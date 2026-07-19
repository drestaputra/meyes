"""Background capture worker with pause, recovery, and safe shutdown."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from contextlib import suppress

from meyes.camera.buffer import LatestFrameBuffer
from meyes.camera.interface import CameraBackend, CameraCapture
from meyes.camera.metrics import FrameRateMeter
from meyes.camera.models import CameraHealth, CameraOptions, CameraStatus
from meyes.camera.state import CameraStateMachine, InvalidCameraTransition
from meyes.util.logging import get_logger

HealthCallback = Callable[[CameraHealth], None]
MonotonicClock = Callable[[], float]


class CameraShutdownError(RuntimeError):
    """Raised if the capture thread cannot stop within its deadline."""


class CameraWorker:
    """Own one camera handle and publish only its latest frame."""

    def __init__(
        self,
        backend: CameraBackend,
        options: CameraOptions,
        *,
        frame_buffer: LatestFrameBuffer | None = None,
        health_callback: HealthCallback | None = None,
        clock: MonotonicClock = time.monotonic,
        retry_delay: float = 0.5,
        error_threshold: int = 3,
    ) -> None:
        if retry_delay < 0:
            raise ValueError("retry_delay cannot be negative")
        if error_threshold < 1:
            raise ValueError("error_threshold must be positive")
        self._backend = backend
        self._options = options
        self._frames = frame_buffer or LatestFrameBuffer()
        self._health_callback = health_callback
        self._clock = clock
        self._retry_delay = retry_delay
        self._error_threshold = error_threshold
        self._state = CameraStateMachine()
        self._health_lock = threading.Lock()
        self._health = CameraHealth()
        self._stop_requested = threading.Event()
        self._pause_requested = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture_lock = threading.Lock()
        self._capture: CameraCapture | None = None
        self._fps = FrameRateMeter()
        self._failure_count = 0
        self._logger = get_logger("CAMERA")

    @property
    def frame_buffer(self) -> LatestFrameBuffer:
        """Expose the latest-frame transport to preview/vision consumers."""
        return self._frames

    @property
    def health(self) -> CameraHealth:
        """Return the latest immutable health snapshot."""
        with self._health_lock:
            return self._health

    @property
    def status(self) -> CameraStatus:
        """Return the validated lifecycle state."""
        return self._state.status

    def start(self) -> None:
        """Start capture in a new worker thread."""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("Camera worker is already running")
        self._stop_requested.clear()
        self._pause_requested.clear()
        self._failure_count = 0
        self._fps.reset()
        self._set_health(CameraStatus.STARTING, "Opening camera")
        self._thread = threading.Thread(target=self._run, name="meyes-camera", daemon=False)
        self._thread.start()

    def pause(self) -> None:
        """Pause capture and release the current camera handle."""
        if self.status in {CameraStatus.STOPPED, CameraStatus.STOPPING, CameraStatus.PAUSED}:
            return
        self._pause_requested.set()
        self._set_health(CameraStatus.PAUSED, "Camera is paused")

    def resume(self) -> None:
        """Resume a paused worker by reopening the configured camera."""
        if self.status is not CameraStatus.PAUSED:
            return
        self._pause_requested.clear()
        self._failure_count = 0
        self._fps.reset()
        self._set_health(CameraStatus.STARTING, "Reopening camera")

    def stop(self, timeout: float = 3.0) -> None:
        """Stop and join the worker before returning."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            if self.status is not CameraStatus.STOPPED:
                self._set_health(CameraStatus.STOPPED, "Camera is stopped")
            return

        if self.status is not CameraStatus.STOPPING:
            self._set_health(CameraStatus.STOPPING, "Stopping camera")
        self._stop_requested.set()
        self._pause_requested.clear()
        first_wait = max(0.0, timeout / 2)
        thread.join(timeout=first_wait)
        if thread.is_alive():
            self._release_capture()
            thread.join(timeout=max(0.0, timeout - first_wait))
        if thread.is_alive():
            self._set_health(
                CameraStatus.ERROR,
                "Camera worker did not stop in time",
                last_error="shutdown timeout",
            )
            raise CameraShutdownError("Camera worker did not stop before timeout")
        self._thread = None

    def wait_for_status(self, status: CameraStatus, timeout: float = 2.0) -> bool:
        """Wait for a lifecycle state, primarily for orchestration and tests."""
        return self._state.wait_for(status, timeout=timeout)

    def _run(self) -> None:
        try:
            while not self._stop_requested.is_set():
                if self._pause_requested.is_set():
                    self._release_capture()
                    self._stop_requested.wait(0.05)
                    continue

                if self._get_capture() is None and not self._open_capture():
                    continue

                capture = self._get_capture()
                if capture is None:
                    continue
                ok, frame = capture.read()
                captured_at = self._clock()

                if self._stop_requested.is_set() or self._pause_requested.is_set():
                    continue
                if not ok or frame is None:
                    self._recover("Camera read failed")
                    continue

                self._failure_count = 0
                measured_fps = self._fps.tick(captured_at)
                self._frames.publish(frame, captured_at)
                self._set_health(
                    CameraStatus.RUNNING,
                    "Camera is ready",
                    measured_fps=measured_fps,
                )
        except Exception as error:
            self._logger.exception("camera_worker_crashed")
            if self.status is not CameraStatus.STOPPING:
                self._set_health(CameraStatus.ERROR, "Camera worker failed", last_error=str(error))
        finally:
            self._release_capture()
            self._frames.clear()
            if self.status is not CameraStatus.STOPPED:
                if self.status is not CameraStatus.STOPPING:
                    with suppress(InvalidCameraTransition):
                        self._state.transition(CameraStatus.STOPPING)
                self._set_health(CameraStatus.STOPPED, "Camera is stopped")

    def _open_capture(self) -> bool:
        if self.status not in {CameraStatus.STARTING, CameraStatus.ERROR, CameraStatus.RECOVERING}:
            self._set_health(CameraStatus.STARTING, "Opening camera")
        elif self.status is not CameraStatus.STARTING:
            self._set_health(CameraStatus.STARTING, "Reopening camera")

        try:
            capture = self._backend.open(self._options)
        except Exception as error:
            self._recover(str(error))
            return False

        with self._capture_lock:
            self._capture = capture

        self._failure_count = 0
        self._fps.reset()
        self._set_health(CameraStatus.RUNNING, "Camera is ready")
        self._logger.info(
            "camera_opened",
            extra={
                "camera_index": self._options.camera_index,
                "width": self._options.width,
                "height": self._options.height,
                "target_fps": self._options.target_fps,
            },
        )
        return True

    def _recover(self, message: str) -> None:
        self._release_capture()
        self._fps.reset()
        if self._stop_requested.is_set() or self._pause_requested.is_set():
            return
        self._failure_count += 1
        status = (
            CameraStatus.ERROR
            if self._failure_count >= self._error_threshold
            else CameraStatus.RECOVERING
        )
        self._set_health(status, message, last_error=message)
        self._logger.warning(
            "camera_recovering",
            extra={"failure_count": self._failure_count, "error": message},
        )
        if self._stop_requested.wait(self._retry_delay):
            return
        if not self._pause_requested.is_set():
            self._set_health(CameraStatus.STARTING, "Retrying camera")

    def _release_capture(self) -> None:
        with self._capture_lock:
            capture, self._capture = self._capture, None
        if capture is not None:
            try:
                capture.release()
            except Exception:
                self._logger.exception("camera_release_failed")

    def _get_capture(self) -> CameraCapture | None:
        with self._capture_lock:
            return self._capture

    def _set_health(
        self,
        status: CameraStatus,
        message: str,
        *,
        measured_fps: float = 0.0,
        last_error: str | None = None,
    ) -> None:
        self._state.transition(status)
        health = CameraHealth(
            status=status,
            message=message,
            camera_index=self._options.camera_index,
            measured_fps=measured_fps,
            failure_count=self._failure_count,
            last_error=last_error,
        )
        with self._health_lock:
            self._health = health
        if self._health_callback is not None:
            self._health_callback(health)
