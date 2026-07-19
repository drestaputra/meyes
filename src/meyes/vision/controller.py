"""Qt-safe orchestration for face, hand, and semantic gesture pipelines."""

from __future__ import annotations

import threading
import time
from collections.abc import Sequence
from functools import partial
from math import isfinite
from typing import cast

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot

from meyes.camera.buffer import LatestFrameBuffer
from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent
from meyes.domain.observations import (
    FaceObservation,
    HandObservation,
    TempleFeatureObservation,
    TempleFeatureStatus,
)
from meyes.gestures.engine import GestureEngine
from meyes.util.logging import get_logger
from meyes.vision.hand_worker import HandVisionHealth, HandVisionWorker
from meyes.vision.interface import FaceBackendFactory, HandBackendFactory
from meyes.vision.temple_features import MonotonicClock, TempleFeatureTracker
from meyes.vision.worker import FaceVisionWorker, VisionHealth, VisionShutdownError, VisionStatus


class VisionController(QObject):
    """Serialize worker output on Qt's main thread with OS input disconnected."""

    observation_changed = Signal(object)
    observation_cleared = Signal()
    health_changed = Signal(object)
    hand_observation_changed = Signal(object)
    hand_observation_cleared = Signal()
    hand_health_changed = Signal(object)
    temple_feature_changed = Signal(object)
    temple_feature_cleared = Signal()
    event_detected = Signal(object)

    _face_result_queued = Signal(object)
    _hand_result_queued = Signal(object)
    _face_health_queued = Signal(object)
    _hand_health_queued = Signal(object)

    def __init__(
        self,
        frames: LatestFrameBuffer,
        backend_factory: FaceBackendFactory,
        gesture_settings: GestureSettings,
        parent: QObject | None = None,
        *,
        hand_backend_factory: HandBackendFactory | None = None,
        hand_target_fps: float = 10.0,
        clock: MonotonicClock | None = None,
    ) -> None:
        super().__init__(parent)
        if hand_target_fps <= 0 or not isfinite(hand_target_fps):
            raise ValueError("Hand target FPS must be finite and greater than zero")
        self._frames = frames
        self._face_backend_factory = backend_factory
        self._hand_backend_factory = hand_backend_factory
        self._hand_target_fps = hand_target_fps
        self._clock = clock or time.monotonic
        self._tracking_timeout = gesture_settings.tracking_timeout_ms / 1000.0
        self._gesture_engine = GestureEngine.from_settings(gesture_settings)
        self._temple_tracker = TempleFeatureTracker(
            max_age=self._tracking_timeout,
            clock=self._clock,
        )
        self._gesture_lock = threading.Lock()
        self._delivery_lock = threading.Lock()
        self._delivery_generation = 0
        self._delivery_enabled = False
        self._result_queue_lock = threading.Lock()
        self._pending_face_result: tuple[int, int, FaceObservation] | None = None
        self._pending_hand_result: tuple[int, int, HandObservation] | None = None
        self._pending_face_health: tuple[int, int, VisionHealth] | None = None
        self._pending_hand_health: tuple[int, int, HandVisionHealth] | None = None
        self._face_dispatch_pending = False
        self._hand_dispatch_pending = False
        self._face_health_dispatch_pending = False
        self._hand_health_dispatch_pending = False
        self._face_worker: FaceVisionWorker | None = None
        self._hand_worker: HandVisionWorker | None = None
        self._face_worker_serial = 0
        self._hand_worker_serial = 0
        self._face_logger = get_logger("FACE")
        self._hand_logger = get_logger("HAND")

        self._face_result_queued.connect(
            self._process_face_result,
            Qt.ConnectionType.QueuedConnection,
        )
        self._hand_result_queued.connect(
            self._process_hand_result,
            Qt.ConnectionType.QueuedConnection,
        )
        self._face_health_queued.connect(
            self._publish_face_health,
            Qt.ConnectionType.QueuedConnection,
        )
        self._hand_health_queued.connect(
            self._publish_hand_health,
            Qt.ConnectionType.QueuedConnection,
        )
        self._watchdog = QTimer(self)
        watchdog_interval = max(5, min(25, gesture_settings.tracking_timeout_ms // 10))
        self._watchdog.setInterval(watchdog_interval)
        self._watchdog.timeout.connect(self.poll_timeouts)

    @property
    def status(self) -> VisionStatus:
        """Return the face pipeline status."""
        if self._face_worker is None:
            return VisionStatus.STOPPED
        return self._face_worker.health.status

    @property
    def hand_status(self) -> VisionStatus:
        """Return the hand pipeline status."""
        if self._hand_worker is None:
            return VisionStatus.STOPPED
        return self._hand_worker.health.status

    @Slot()
    def start(self) -> None:
        """Start or resume all configured local vision workers."""
        self._enable_delivery()
        self._start_face_worker()
        self._start_hand_worker()
        if not self._watchdog.isActive():
            self._watchdog.start()

    @Slot()
    def suspend(self) -> None:
        """Invalidate all pending results and reset paired gesture state."""
        self._disable_delivery()
        with self._result_queue_lock:
            self._pending_face_result = None
            self._pending_hand_result = None
            self._pending_face_health = None
            self._pending_hand_health = None
            self._face_dispatch_pending = False
            self._hand_dispatch_pending = False
            self._face_health_dispatch_pending = False
            self._hand_health_dispatch_pending = False
        self._watchdog.stop()
        if self._face_worker is not None:
            self._face_worker.invalidate_observations()
        if self._hand_worker is not None:
            self._hand_worker.invalidate_observations()
        self._temple_tracker.reset()
        with self._gesture_lock:
            self._gesture_engine.reset()
        self.observation_cleared.emit()
        self.hand_observation_cleared.emit()
        self.temple_feature_cleared.emit()

    @Slot()
    def stop(self) -> None:
        """Stop every worker even when another worker reports a timeout."""
        self.suspend()
        self._stop_face_worker()
        self._stop_hand_worker()

    @Slot()
    def poll_timeouts(self) -> None:
        """Publish one expiry transition when paired features become stale."""
        if not self._delivery_is_enabled():
            return
        expired = self._temple_tracker.expire()
        if expired is not None:
            self.temple_feature_changed.emit(expired)

    def _start_face_worker(self) -> None:
        worker = self._face_worker
        if worker is not None:
            if worker.health.status in {VisionStatus.STARTING, VisionStatus.RUNNING}:
                worker.resume_observations()
                return
            if worker.health.status is VisionStatus.STOPPING:
                return
            try:
                worker.stop()
            except VisionShutdownError:
                self._face_logger.exception("face_restart_shutdown_timeout")
                return
        with self._result_queue_lock:
            self._face_worker_serial += 1
            serial = self._face_worker_serial
        self._face_worker = FaceVisionWorker(
            self._frames,
            self._face_backend_factory,
            observation_callback=partial(self._queue_face_result, serial),
            health_callback=partial(self._queue_face_health, serial),
        )
        self._face_worker.start()

    def _start_hand_worker(self) -> None:
        if self._hand_backend_factory is None:
            return
        worker = self._hand_worker
        if worker is not None:
            if worker.health.status in {VisionStatus.STARTING, VisionStatus.RUNNING}:
                worker.resume_observations()
                return
            if worker.health.status is VisionStatus.STOPPING:
                return
            try:
                worker.stop()
            except VisionShutdownError:
                self._hand_logger.exception("hand_restart_shutdown_timeout")
                return
        with self._result_queue_lock:
            self._hand_worker_serial += 1
            serial = self._hand_worker_serial
        self._hand_worker = HandVisionWorker(
            self._frames,
            self._hand_backend_factory,
            observation_callback=partial(self._queue_hand_result, serial),
            health_callback=partial(self._queue_hand_health, serial),
            target_fps=self._hand_target_fps,
        )
        self._hand_worker.start()

    def _stop_face_worker(self) -> None:
        worker = self._face_worker
        if worker is None:
            return
        try:
            worker.stop()
        except VisionShutdownError as error:
            self._face_logger.exception("face_shutdown_timeout")
            self._queue_face_health(
                self._face_worker_serial,
                VisionHealth(
                    status=VisionStatus.ERROR,
                    message="Face pipeline did not stop in time",
                    last_error=str(error),
                ),
            )
        else:
            self._face_worker = None

    def _stop_hand_worker(self) -> None:
        worker = self._hand_worker
        if worker is None:
            return
        try:
            worker.stop()
        except VisionShutdownError as error:
            self._hand_logger.exception("hand_shutdown_timeout")
            self._queue_hand_health(
                self._hand_worker_serial,
                HandVisionHealth(
                    status=VisionStatus.ERROR,
                    message="Hand pipeline did not stop in time",
                    last_error=str(error),
                ),
            )
        else:
            self._hand_worker = None

    def _queue_face_result(self, serial: int, observation: FaceObservation) -> None:
        token = self._delivery_token()
        if token is None:
            return
        should_dispatch = False
        with self._result_queue_lock:
            if serial != self._face_worker_serial:
                return
            self._pending_face_result = (token, serial, observation)
            if not self._face_dispatch_pending:
                self._face_dispatch_pending = True
                should_dispatch = True
        if should_dispatch:
            self._face_result_queued.emit(None)

    def _queue_hand_result(self, serial: int, observation: HandObservation) -> None:
        token = self._delivery_token()
        if token is None:
            return
        should_dispatch = False
        with self._result_queue_lock:
            if serial != self._hand_worker_serial:
                return
            self._pending_hand_result = (token, serial, observation)
            if not self._hand_dispatch_pending:
                self._hand_dispatch_pending = True
                should_dispatch = True
        if should_dispatch:
            self._hand_result_queued.emit(None)

    def _queue_face_health(self, serial: int, health: VisionHealth) -> None:
        generation, delivery_enabled = self._delivery_snapshot()
        if not delivery_enabled and not self._terminal_health_status(health.status):
            return
        should_dispatch = False
        with self._result_queue_lock:
            if serial != self._face_worker_serial:
                return
            self._pending_face_health = (generation, serial, health)
            if not self._face_health_dispatch_pending:
                self._face_health_dispatch_pending = True
                should_dispatch = True
        if should_dispatch:
            self._face_health_queued.emit(None)

    def _queue_hand_health(self, serial: int, health: HandVisionHealth) -> None:
        generation, delivery_enabled = self._delivery_snapshot()
        if not delivery_enabled and not self._terminal_health_status(health.status):
            return
        should_dispatch = False
        with self._result_queue_lock:
            if serial != self._hand_worker_serial:
                return
            self._pending_hand_health = (generation, serial, health)
            if not self._hand_health_dispatch_pending:
                self._hand_health_dispatch_pending = True
                should_dispatch = True
        if should_dispatch:
            self._hand_health_queued.emit(None)

    @Slot(object)
    def _process_face_result(self, _marker: object) -> None:
        with self._result_queue_lock:
            payload = self._pending_face_result
            self._pending_face_result = None
            self._face_dispatch_pending = False
        accepted = self._accepted_observation_payload(
            payload,
            current_serial=self._face_worker_serial,
        )
        if not isinstance(accepted, FaceObservation):
            return
        if not self._capture_is_fresh(accepted.capture_timestamp):
            with self._gesture_lock:
                self._gesture_engine.reset()
            self.observation_cleared.emit()
            self.poll_timeouts()
            return
        face_added = self._temple_tracker.update_face(accepted)
        self.observation_changed.emit(accepted)
        if face_added:
            refreshed = self._temple_tracker.recompute_latest_hand()
            if refreshed is not None:
                self.temple_feature_changed.emit(refreshed)
        with self._gesture_lock:
            events = self._gesture_engine.update_face(accepted)
        self._publish_events(events)

    @Slot(object)
    def _process_hand_result(self, _marker: object) -> None:
        with self._result_queue_lock:
            payload = self._pending_hand_result
            self._pending_hand_result = None
            self._hand_dispatch_pending = False
        accepted = self._accepted_observation_payload(
            payload,
            current_serial=self._hand_worker_serial,
        )
        if not isinstance(accepted, HandObservation):
            return
        if not self._capture_is_fresh(accepted.capture_timestamp):
            self.hand_observation_cleared.emit()
            self.poll_timeouts()
            return
        feature = self._temple_tracker.update_hand(accepted)
        self.hand_observation_changed.emit(accepted)
        if feature.status is not TempleFeatureStatus.OUT_OF_ORDER:
            self.temple_feature_changed.emit(feature)

    @Slot(object)
    def _publish_face_health(self, _marker: object) -> None:
        with self._result_queue_lock:
            payload = self._pending_face_health
            self._pending_face_health = None
            self._face_health_dispatch_pending = False
        accepted = self._accepted_health_payload(
            payload,
            current_serial=self._face_worker_serial,
        )
        if isinstance(accepted, VisionHealth):
            self.health_changed.emit(accepted)

    @Slot(object)
    def _publish_hand_health(self, _marker: object) -> None:
        with self._result_queue_lock:
            payload = self._pending_hand_health
            self._pending_hand_health = None
            self._hand_health_dispatch_pending = False
        accepted = self._accepted_health_payload(
            payload,
            current_serial=self._hand_worker_serial,
        )
        if isinstance(accepted, HandVisionHealth):
            self.hand_health_changed.emit(accepted)

    def _publish_events(self, events: Sequence[GestureEvent]) -> None:
        for event in events:
            self._face_logger.info(
                "gesture_event",
                extra={
                    "event_type": event.type.value,
                    "source_sequence": event.source_sequence,
                    "duration_ms": round(event.duration_ms, 1),
                },
            )
            self.event_detected.emit(event)

    def _enable_delivery(self) -> None:
        with self._delivery_lock:
            if not self._delivery_enabled:
                self._delivery_generation += 1
                self._delivery_enabled = True

    def _disable_delivery(self) -> None:
        with self._delivery_lock:
            self._delivery_generation += 1
            self._delivery_enabled = False

    def _delivery_token(self) -> int | None:
        with self._delivery_lock:
            return self._delivery_generation if self._delivery_enabled else None

    def _delivery_snapshot(self) -> tuple[int, bool]:
        with self._delivery_lock:
            return self._delivery_generation, self._delivery_enabled

    def _delivery_is_enabled(self) -> bool:
        with self._delivery_lock:
            return self._delivery_enabled

    def _accepted_observation_payload(
        self,
        payload: object,
        *,
        current_serial: int,
    ) -> object | None:
        if not isinstance(payload, tuple) or len(payload) != 3:
            return None
        generation, serial, observation = cast(tuple[object, object, object], payload)
        if (
            not isinstance(generation, int)
            or not isinstance(serial, int)
            or serial != current_serial
        ):
            return None
        with self._delivery_lock:
            if not self._delivery_enabled or generation != self._delivery_generation:
                return None
        return observation

    def _accepted_health_payload(
        self,
        payload: object,
        *,
        current_serial: int,
    ) -> object | None:
        if not isinstance(payload, tuple) or len(payload) != 3:
            return None
        generation, serial, health = cast(tuple[object, object, object], payload)
        if (
            not isinstance(generation, int)
            or not isinstance(serial, int)
            or serial != current_serial
            or not isinstance(health, (VisionHealth, HandVisionHealth))
        ):
            return None
        with self._delivery_lock:
            if generation != self._delivery_generation:
                return None
            if not self._delivery_enabled and not self._terminal_health_status(health.status):
                return None
        return health

    def _capture_is_fresh(self, capture_timestamp: float) -> bool:
        now = self._clock()
        if not isfinite(now) or not isfinite(capture_timestamp):
            return False
        age = now - capture_timestamp
        return 0.0 <= age <= self._tracking_timeout

    @staticmethod
    def _terminal_health_status(status: VisionStatus) -> bool:
        return status in {
            VisionStatus.STOPPING,
            VisionStatus.STOPPED,
            VisionStatus.ERROR,
        }


def face_observation(value: object) -> FaceObservation:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, FaceObservation):
        raise TypeError("Expected FaceObservation")
    return value


def hand_observation(value: object) -> HandObservation:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, HandObservation):
        raise TypeError("Expected HandObservation")
    return value


def vision_health(value: object) -> VisionHealth:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, VisionHealth):
        raise TypeError("Expected VisionHealth")
    return value


def hand_vision_health(value: object) -> HandVisionHealth:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, HandVisionHealth):
        raise TypeError("Expected HandVisionHealth")
    return value


def temple_feature_observation(value: object) -> TempleFeatureObservation:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, TempleFeatureObservation):
        raise TypeError("Expected TempleFeatureObservation")
    return value


def gesture_event(value: object) -> GestureEvent:
    """Validate a Qt object signal payload at the UI boundary."""
    if not isinstance(value, GestureEvent):
        raise TypeError("Expected GestureEvent")
    return value
