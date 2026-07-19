"""Latest-frame face observation worker."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from meyes.camera.buffer import LatestFrameBuffer
from meyes.camera.metrics import FrameRateMeter
from meyes.domain.observations import FaceObservation
from meyes.util.logging import get_logger
from meyes.vision.buffer import LatestFaceObservationBuffer
from meyes.vision.interface import FaceBackendFactory, FaceObservationBackend


class VisionStatus(StrEnum):
    """Face pipeline lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    STOPPING = "stopping"


@dataclass(frozen=True, slots=True)
class VisionHealth:
    """Latest face-pipeline status for diagnostics."""

    status: VisionStatus = VisionStatus.STOPPED
    message: str = "Face pipeline is stopped"
    inference_fps: float = 0.0
    face_detected: bool = False
    processing_latency_ms: float = 0.0
    last_error: str | None = None


VisionCallback = Callable[[FaceObservation], None]
HealthCallback = Callable[[VisionHealth], None]


class VisionShutdownError(RuntimeError):
    """Raised if face inference cannot stop before its deadline."""


class FaceVisionWorker:
    """Process only the newest camera frame on a dedicated thread."""

    def __init__(
        self,
        frames: LatestFrameBuffer,
        backend_factory: FaceBackendFactory,
        *,
        observations: LatestFaceObservationBuffer | None = None,
        observation_callback: VisionCallback | None = None,
        health_callback: HealthCallback | None = None,
        poll_timeout: float = 0.1,
    ) -> None:
        self._frames = frames
        self._backend_factory = backend_factory
        self._backend: FaceObservationBackend | None = None
        self._observations = observations or LatestFaceObservationBuffer()
        self._observation_callback = observation_callback
        self._health_callback = health_callback
        self._poll_timeout = poll_timeout
        self._status_lock = threading.Lock()
        self._health = VisionHealth()
        self._stop_requested = threading.Event()
        self._thread: threading.Thread | None = None
        self._fps = FrameRateMeter(window_size=30)
        self._logger = get_logger("FACE")

    @property
    def observation_buffer(self) -> LatestFaceObservationBuffer:
        """Expose latest face observations to gesture consumers."""
        return self._observations

    @property
    def health(self) -> VisionHealth:
        """Return the latest immutable pipeline health."""
        with self._status_lock:
            return self._health

    def start(self) -> None:
        """Start the face inference thread."""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("Face vision worker is already running")
        self._stop_requested.clear()
        self._fps.reset()
        self._set_health(VisionStatus.STARTING, "Starting face pipeline")
        self._thread = threading.Thread(target=self._run, name="meyes-face", daemon=False)
        self._thread.start()

    def stop(self, timeout: float = 4.0) -> None:
        """Stop inference, close the backend, and clear observations."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            self._set_health(VisionStatus.STOPPED, "Face pipeline is stopped")
            return
        self._set_health(VisionStatus.STOPPING, "Stopping face pipeline")
        self._stop_requested.set()
        thread.join(timeout=timeout)
        if thread.is_alive():
            self._set_health(
                VisionStatus.ERROR,
                "Face pipeline did not stop in time",
                last_error="shutdown timeout",
            )
            raise VisionShutdownError("Face pipeline did not stop before timeout")
        self._thread = None

    def invalidate_observations(self) -> None:
        """Clear stale face state when camera capture is unavailable."""
        self._observations.clear()

    def _run(self) -> None:
        last_sequence = 0
        crashed = False
        try:
            self._backend = self._backend_factory()
            self._set_health(VisionStatus.RUNNING, "Waiting for camera frames")
            while not self._stop_requested.is_set():
                packet = self._frames.wait_for_new(
                    after_sequence=last_sequence,
                    timeout=self._poll_timeout,
                )
                if packet is None:
                    continue
                last_sequence = packet.sequence
                backend = self._backend
                if backend is None:
                    raise RuntimeError("Face backend was not initialized")
                observation = backend.process(packet)
                inference_fps = self._fps.tick(time.monotonic())
                self._observations.publish(observation)
                self._set_health(
                    VisionStatus.RUNNING,
                    "Face detected" if observation.face_detected else "No face detected",
                    inference_fps=inference_fps,
                    face_detected=observation.face_detected,
                    processing_latency_ms=observation.processing_latency_ms,
                )
                if self._observation_callback is not None:
                    self._observation_callback(observation)
        except Exception as error:
            crashed = True
            self._logger.exception("face_worker_crashed")
            self._set_health(VisionStatus.ERROR, "Face pipeline failed", last_error=str(error))
        finally:
            try:
                if self._backend is not None:
                    self._backend.close()
            except Exception:
                self._logger.exception("face_backend_close_failed")
            self._backend = None
            self._observations.clear()
            if not crashed:
                self._set_health(VisionStatus.STOPPED, "Face pipeline is stopped")

    def _set_health(
        self,
        status: VisionStatus,
        message: str,
        *,
        inference_fps: float = 0.0,
        face_detected: bool = False,
        processing_latency_ms: float = 0.0,
        last_error: str | None = None,
    ) -> None:
        health = VisionHealth(
            status=status,
            message=message,
            inference_fps=inference_fps,
            face_detected=face_detected,
            processing_latency_ms=processing_latency_ms,
            last_error=last_error,
        )
        with self._status_lock:
            self._health = health
        if self._health_callback is not None:
            self._health_callback(health)
