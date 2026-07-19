"""Lower-cadence latest-frame hand observation worker."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite

from meyes.camera.buffer import LatestFrameBuffer
from meyes.camera.metrics import FrameRateMeter
from meyes.domain.observations import HandObservation
from meyes.util.logging import get_logger
from meyes.vision.buffer import LatestHandObservationBuffer
from meyes.vision.interface import HandBackendFactory, HandObservationBackend
from meyes.vision.result_gate import ObservationResultGate
from meyes.vision.worker import VisionShutdownError, VisionStatus


@dataclass(frozen=True, slots=True)
class HandVisionHealth:
    """Latest hand-pipeline status for diagnostics."""

    status: VisionStatus = VisionStatus.STOPPED
    message: str = "Hand pipeline is stopped"
    inference_fps: float = 0.0
    hand_count: int = 0
    processing_latency_ms: float = 0.0
    last_error: str | None = None


HandObservationCallback = Callable[[HandObservation], None]
HandHealthCallback = Callable[[HandVisionHealth], None]
MonotonicClock = Callable[[], float]


class HandVisionWorker:
    """Process only fresh frames at a bounded hand-inference cadence."""

    def __init__(
        self,
        frames: LatestFrameBuffer,
        backend_factory: HandBackendFactory,
        *,
        observations: LatestHandObservationBuffer | None = None,
        observation_callback: HandObservationCallback | None = None,
        health_callback: HandHealthCallback | None = None,
        target_fps: float = 10.0,
        poll_timeout: float = 0.1,
        clock: MonotonicClock = time.monotonic,
    ) -> None:
        if target_fps <= 0 or not isfinite(target_fps):
            raise ValueError("Hand target FPS must be finite and greater than zero")
        self._frames = frames
        self._backend_factory = backend_factory
        self._backend: HandObservationBackend | None = None
        self._observations = observations or LatestHandObservationBuffer()
        self._observation_callback = observation_callback
        self._health_callback = health_callback
        self._minimum_interval = 1.0 / target_fps
        self._poll_timeout = poll_timeout
        self._clock = clock
        self._status_lock = threading.Lock()
        self._health = HandVisionHealth()
        self._stop_requested = threading.Event()
        self._thread: threading.Thread | None = None
        self._fps = FrameRateMeter(window_size=20)
        self._results = ObservationResultGate()
        self._logger = get_logger("HAND")

    @property
    def observation_buffer(self) -> LatestHandObservationBuffer:
        """Expose latest hand observations to gesture consumers."""
        return self._observations

    @property
    def health(self) -> HandVisionHealth:
        """Return the latest immutable pipeline health."""
        with self._status_lock:
            return self._health

    def start(self) -> None:
        """Start the hand inference thread."""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("Hand vision worker is already running")
        self._stop_requested.clear()
        self._fps.reset()
        self._results.enable()
        self._set_health(VisionStatus.STARTING, "Starting hand pipeline")
        self._thread = threading.Thread(target=self._run, name="meyes-hand", daemon=False)
        self._thread.start()

    def stop(self, timeout: float = 4.0) -> None:
        """Stop inference, close the backend, and clear observations."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            self.invalidate_observations()
            self._set_health(VisionStatus.STOPPED, "Hand pipeline is stopped")
            return
        self._set_health(VisionStatus.STOPPING, "Stopping hand pipeline")
        self._stop_requested.set()
        self.invalidate_observations()
        thread.join(timeout=timeout)
        if thread.is_alive():
            self._set_health(
                VisionStatus.ERROR,
                "Hand pipeline did not stop in time",
                last_error="shutdown timeout",
            )
            raise VisionShutdownError("Hand pipeline did not stop before timeout")
        self._thread = None

    def invalidate_observations(self) -> None:
        """Clear stale hand state when camera capture is unavailable."""
        self._results.disable(self._observations.clear)

    def resume_observations(self) -> None:
        """Allow new camera frames to publish after a suspension."""
        self._results.enable()

    def _run(self) -> None:
        last_sequence = 0
        next_due = self._clock()
        crashed = False
        try:
            self._backend = self._backend_factory()
            self._set_health(VisionStatus.RUNNING, "Waiting for camera frames")
            while not self._stop_requested.is_set():
                remaining = next_due - self._clock()
                if remaining > 0:
                    self._stop_requested.wait(min(remaining, self._poll_timeout))
                    continue
                packet = self._frames.wait_for_new(
                    after_sequence=last_sequence,
                    timeout=self._poll_timeout,
                )
                if packet is None:
                    continue
                last_sequence = packet.sequence
                result_token = self._results.token()
                if result_token is None:
                    continue
                backend = self._backend
                if backend is None:
                    raise RuntimeError("Hand backend was not initialized")
                inference_started = self._clock()
                next_due = inference_started + self._minimum_interval
                observation = backend.process(packet)

                def publish_result(current: HandObservation = observation) -> None:
                    inference_fps = self._fps.tick(time.monotonic())
                    self._observations.publish(current)
                    hand_count = len(current.hands)
                    self._set_health(
                        VisionStatus.RUNNING,
                        f"{hand_count} hand{'s' if hand_count != 1 else ''} detected",
                        inference_fps=inference_fps,
                        hand_count=hand_count,
                        processing_latency_ms=current.processing_latency_ms,
                    )
                    if self._observation_callback is not None:
                        self._observation_callback(current)

                self._results.publish_if_current(
                    result_token,
                    cancelled=self._stop_requested.is_set,
                    publish=publish_result,
                )
        except Exception as error:
            crashed = True
            self._logger.exception("hand_worker_crashed")
            self._set_health(VisionStatus.ERROR, "Hand pipeline failed", last_error=str(error))
        finally:
            try:
                if self._backend is not None:
                    self._backend.close()
            except Exception:
                self._logger.exception("hand_backend_close_failed")
            self._backend = None
            self.invalidate_observations()
            if not crashed:
                self._set_health(VisionStatus.STOPPED, "Hand pipeline is stopped")

    def _set_health(
        self,
        status: VisionStatus,
        message: str,
        *,
        inference_fps: float = 0.0,
        hand_count: int = 0,
        processing_latency_ms: float = 0.0,
        last_error: str | None = None,
    ) -> None:
        health = HandVisionHealth(
            status=status,
            message=message,
            inference_fps=inference_fps,
            hand_count=hand_count,
            processing_latency_ms=processing_latency_ms,
            last_error=last_error,
        )
        with self._status_lock:
            self._health = health
        if self._health_callback is not None:
            self._health_callback(health)
