"""Qt-safe orchestration for face inference and semantic gestures."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal, Slot

from meyes.camera.buffer import LatestFrameBuffer
from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent
from meyes.domain.observations import FaceObservation
from meyes.gestures.engine import GestureEngine
from meyes.util.logging import get_logger
from meyes.vision.interface import FaceBackendFactory
from meyes.vision.worker import FaceVisionWorker, VisionHealth, VisionShutdownError, VisionStatus


class VisionController(QObject):
    """Bridge worker callbacks into Qt while keeping OS input disconnected."""

    observation_changed = Signal(object)
    observation_cleared = Signal()
    health_changed = Signal(object)
    event_detected = Signal(object)

    def __init__(
        self,
        frames: LatestFrameBuffer,
        backend_factory: FaceBackendFactory,
        gesture_settings: GestureSettings,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._frames = frames
        self._backend_factory = backend_factory
        self._gesture_engine = GestureEngine.from_settings(gesture_settings)
        self._gesture_lock = threading.Lock()
        self._worker: FaceVisionWorker | None = None
        self._logger = get_logger("FACE")

    @property
    def status(self) -> VisionStatus:
        """Return the current pipeline status."""
        if self._worker is None:
            return VisionStatus.STOPPED
        return self._worker.health.status

    @Slot()
    def start(self) -> None:
        """Start a new face worker when capture becomes available."""
        if self._worker is not None and self._worker.health.status in {
            VisionStatus.STARTING,
            VisionStatus.RUNNING,
            VisionStatus.STOPPING,
        }:
            return
        self._worker = FaceVisionWorker(
            self._frames,
            self._backend_factory,
            observation_callback=self._on_observation,
            health_callback=self._on_health,
        )
        self._worker.start()

    @Slot()
    def suspend(self) -> None:
        """Invalidate gesture and observation state while capture is unavailable."""
        with self._gesture_lock:
            self._gesture_engine.reset()
        if self._worker is not None:
            self._worker.invalidate_observations()
        self.observation_cleared.emit()

    @Slot()
    def stop(self) -> None:
        """Stop inference and reset all face-derived gesture state."""
        self.suspend()
        worker, self._worker = self._worker, None
        if worker is None:
            return
        try:
            worker.stop()
        except VisionShutdownError as error:
            self._logger.exception("vision_shutdown_timeout")
            self.health_changed.emit(
                VisionHealth(
                    status=VisionStatus.ERROR,
                    message="Face pipeline did not stop in time",
                    last_error=str(error),
                )
            )

    def _on_observation(self, observation: FaceObservation) -> None:
        self.observation_changed.emit(observation)
        with self._gesture_lock:
            events = self._gesture_engine.update_face(observation)
        for event in events:
            self._logger.info(
                "gesture_event",
                extra={
                    "event_type": event.type.value,
                    "source_sequence": event.source_sequence,
                    "duration_ms": round(event.duration_ms, 1),
                },
            )
            self.event_detected.emit(event)

    def _on_health(self, health: VisionHealth) -> None:
        self.health_changed.emit(health)


def face_observation(value: object) -> FaceObservation:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, FaceObservation):
        raise TypeError("Expected FaceObservation")
    return value


def vision_health(value: object) -> VisionHealth:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, VisionHealth):
        raise TypeError("Expected VisionHealth")
    return value


def gesture_event(value: object) -> GestureEvent:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, GestureEvent):
        raise TypeError("Expected GestureEvent")
    return value
