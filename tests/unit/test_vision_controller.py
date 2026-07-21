"""Qt vision/gesture orchestration tests in no-input safe mode."""

from __future__ import annotations

import threading
import time
from typing import Any, cast

import numpy as np
import pytest
from pytestqt.qtbot import QtBot

from meyes.camera.buffer import LatestFrameBuffer
from meyes.camera.models import FramePacket
from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import (
    DetectedHand,
    FaceObservation,
    GazeFeatureObservation,
    GazeFeatureStatus,
    HandObservation,
    HandSide,
    NormalizedPoint,
    TempleFeatureObservation,
    TempleFeatureStatus,
    TempleProximity,
)
from meyes.gestures.temple_proximity import ProximityState, TempleProximitySnapshot
from meyes.vision.controller import VisionController, gaze_feature_observation
from meyes.vision.hand_worker import HandVisionHealth
from meyes.vision.worker import VisionHealth, VisionShutdownError, VisionStatus


class SequencedFaceBackend:
    def __init__(self, openness: dict[int, tuple[float, float]]) -> None:
        self._openness = openness
        self.closed = threading.Event()

    def process(self, packet: FramePacket) -> FaceObservation:
        left, right = self._openness[packet.sequence]
        return FaceObservation(
            source_sequence=packet.sequence,
            capture_timestamp=packet.capture_timestamp,
            processed_timestamp=packet.capture_timestamp + 0.01,
            face_detected=True,
            left_eye_openness=left,
            right_eye_openness=right,
        )

    def close(self) -> None:
        self.closed.set()


class FeatureFaceBackend:
    def __init__(self) -> None:
        self.closed = threading.Event()

    def process(self, packet: FramePacket) -> FaceObservation:
        landmarks = [NormalizedPoint(0.5, 0.5) for _ in range(478)]
        for index in (127, 162, 234):
            landmarks[index] = NormalizedPoint(0.2, 0.4)
        for index in (356, 389, 454):
            landmarks[index] = NormalizedPoint(0.8, 0.4)
        landmarks[362] = NormalizedPoint(0.55, 0.45)
        landmarks[263] = NormalizedPoint(0.75, 0.45)
        landmarks[386] = NormalizedPoint(0.65, 0.40)
        landmarks[374] = NormalizedPoint(0.65, 0.50)
        landmarks[33] = NormalizedPoint(0.25, 0.45)
        landmarks[133] = NormalizedPoint(0.45, 0.45)
        landmarks[159] = NormalizedPoint(0.35, 0.40)
        landmarks[145] = NormalizedPoint(0.35, 0.50)
        height, width = packet.frame.shape[:2]
        return FaceObservation(
            source_sequence=packet.sequence,
            capture_timestamp=packet.capture_timestamp,
            processed_timestamp=packet.capture_timestamp + 0.01,
            face_detected=True,
            left_eye_openness=0.9,
            right_eye_openness=0.9,
            left_iris_center=NormalizedPoint(0.65, 0.45),
            right_iris_center=NormalizedPoint(0.35, 0.45),
            landmarks=tuple(landmarks),
            frame_width=width,
            frame_height=height,
        )

    def close(self) -> None:
        self.closed.set()


class SlowFeatureFaceBackend(FeatureFaceBackend):
    def process(self, packet: FramePacket) -> FaceObservation:
        time.sleep(0.12)
        return super().process(packet)


class FeatureHandBackend:
    def __init__(self) -> None:
        self.closed = threading.Event()

    def process(self, packet: FramePacket) -> HandObservation:
        landmarks = [NormalizedPoint(0.5, 0.5) for _ in range(21)]
        landmarks[8] = NormalizedPoint(0.2, 0.4)
        height, width = packet.frame.shape[:2]
        return HandObservation(
            source_sequence=packet.sequence,
            capture_timestamp=packet.capture_timestamp,
            processed_timestamp=packet.capture_timestamp + 0.02,
            hands=(
                DetectedHand(
                    side=HandSide.RIGHT,
                    confidence=0.9,
                    landmarks=tuple(landmarks),
                ),
            ),
            frame_width=width,
            frame_height=height,
        )

    def close(self) -> None:
        self.closed.set()


class FakeClock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class StopStub:
    def __init__(self, health: VisionHealth | HandVisionHealth, *, fail: bool) -> None:
        self.health = health
        self.fail = fail
        self.invalidated = False
        self.stop_called = False

    def invalidate_observations(self) -> None:
        self.invalidated = True

    def resume_observations(self) -> None:
        pass

    def stop(self) -> None:
        self.stop_called = True
        if self.fail:
            raise VisionShutdownError("test timeout")


def feature_face_observation(sequence: int, captured: float) -> FaceObservation:
    return FeatureFaceBackend().process(
        FramePacket(
            sequence=sequence,
            capture_timestamp=captured,
            frame=np.zeros((480, 640, 3), dtype=np.uint8),
        )
    )


def feature_hand_observation(
    sequence: int,
    captured: float,
    *,
    fingertip_x: float = 0.2,
) -> HandObservation:
    landmarks = [NormalizedPoint(0.5, 0.5) for _ in range(21)]
    landmarks[8] = NormalizedPoint(fingertip_x, 0.4)
    return HandObservation(
        source_sequence=sequence,
        capture_timestamp=captured,
        processed_timestamp=captured + 0.02,
        hands=(
            DetectedHand(
                side=HandSide.RIGHT,
                confidence=0.9,
                landmarks=tuple(landmarks),
            ),
        ),
        frame_width=640,
        frame_height=480,
    )


def direct_temple_feature(
    sequence: int,
    captured: float,
    *,
    right_ratio: float,
    left_ratio: float | None = None,
) -> TempleFeatureObservation:
    proximities = []
    if left_ratio is not None:
        proximities.append(TempleProximity(HandSide.LEFT, left_ratio, 0.9))
    proximities.append(TempleProximity(HandSide.RIGHT, right_ratio, 0.9))
    return TempleFeatureObservation(
        source_sequence=sequence,
        capture_timestamp=captured,
        processed_timestamp=captured + 0.001,
        status=TempleFeatureStatus.READY,
        proximities=tuple(proximities),
    )


def publish_and_wait(
    qtbot: QtBot,
    controller: VisionController,
    frames: LatestFrameBuffer,
    timestamp: float,
) -> None:
    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), timestamp)


def test_controller_emits_semantic_wink_without_action_side_effects(qtbot: QtBot) -> None:
    frames = LatestFrameBuffer()
    backend = SequencedFaceBackend(
        {
            1: (0.9, 0.9),
            2: (0.2, 0.9),
            3: (0.2, 0.9),
        }
    )
    clock = FakeClock(1.0)
    controller = VisionController(
        frames,
        lambda: backend,
        GestureSettings(),
        clock=clock,
    )
    events: list[GestureEvent] = []
    controller.event_detected.connect(events.append)
    controller.start()

    publish_and_wait(qtbot, controller, frames, 1.00)
    clock.now = 1.05
    publish_and_wait(qtbot, controller, frames, 1.05)
    clock.now = 1.20
    with qtbot.waitSignal(controller.event_detected, timeout=1000):
        frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.20)
    controller.stop()

    assert [event.type for event in events] == [GestureEventType.LEFT_WINK]
    assert backend.closed.is_set()


def test_suspend_clears_candidate_and_observation(qtbot: QtBot) -> None:
    frames = LatestFrameBuffer()
    backend = SequencedFaceBackend({1: (0.9, 0.9), 2: (0.2, 0.9), 3: (0.2, 0.9)})
    clock = FakeClock(1.0)
    controller = VisionController(
        frames,
        lambda: backend,
        GestureSettings(),
        clock=clock,
    )
    events: list[GestureEvent] = []
    controller.event_detected.connect(events.append)
    controller.start()

    publish_and_wait(qtbot, controller, frames, 1.00)
    clock.now = 1.05
    publish_and_wait(qtbot, controller, frames, 1.05)
    with qtbot.waitSignal(controller.observation_cleared, timeout=1000):
        controller.suspend()
    controller.start()
    clock.now = 1.20
    publish_and_wait(qtbot, controller, frames, 1.20)
    controller.stop()

    assert events == []


def test_controller_composes_hand_features_and_watchdog_without_actions(qtbot: QtBot) -> None:
    frames = LatestFrameBuffer()
    face_backend = FeatureFaceBackend()
    hand_backend = FeatureHandBackend()
    clock = FakeClock(10.0)
    controller = VisionController(
        frames,
        lambda: face_backend,
        GestureSettings(),
        hand_backend_factory=lambda: hand_backend,
        hand_target_fps=50.0,
        clock=clock,
    )
    hand_observations: list[HandObservation] = []
    features: list[TempleFeatureObservation] = []
    events: list[GestureEvent] = []
    controller.hand_observation_changed.connect(hand_observations.append)
    controller.temple_feature_changed.connect(features.append)
    controller.event_detected.connect(events.append)
    controller.start()

    frames.publish(np.zeros((480, 640, 3), dtype=np.uint8), 9.95)
    qtbot.waitUntil(lambda: len(hand_observations) >= 1, timeout=1000)
    qtbot.wait(30)
    clock.now = 10.05
    frames.publish(np.zeros((480, 640, 3), dtype=np.uint8), 10.04)
    qtbot.waitUntil(
        lambda: any(feature.status is TempleFeatureStatus.READY for feature in features),
        timeout=1000,
    )

    ready = next(feature for feature in features if feature.status is TempleFeatureStatus.READY)
    right = ready.proximity(HandSide.RIGHT)
    assert right is not None
    assert right.distance_ratio == 0.0
    assert events == []

    clock.now = 10.31
    qtbot.waitUntil(
        lambda: features[-1].status is TempleFeatureStatus.EXPIRED,
        timeout=1000,
    )
    assert features[-1].status is TempleFeatureStatus.EXPIRED
    feature_count = len(features)
    controller.stop()
    qtbot.wait(60)
    assert len(features) == feature_count
    assert face_backend.closed.is_set()
    assert hand_backend.closed.is_set()


def test_raw_temple_features_drive_stabilized_proximity_without_events(qtbot: QtBot) -> None:
    clock = FakeClock(10.0)
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        hand_backend_factory=FeatureHandBackend,
        clock=clock,
    )
    snapshots: list[TempleProximitySnapshot] = []
    events: list[GestureEvent] = []
    controller.temple_proximity_changed.connect(snapshots.append)
    controller.event_detected.connect(events.append)
    controller.start()
    controller._watchdog.stop()

    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        controller._queue_face_result(
            controller._face_worker_serial,
            feature_face_observation(1, 10.0),
        )
    with qtbot.waitSignal(controller.temple_feature_changed, timeout=1000):
        controller._queue_hand_result(
            controller._hand_worker_serial,
            feature_hand_observation(1, 10.0),
        )

    clock.now = 10.19
    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        controller._queue_face_result(
            controller._face_worker_serial,
            feature_face_observation(2, 10.19),
        )
    with qtbot.waitSignal(controller.temple_proximity_changed, timeout=1000):
        controller._queue_hand_result(
            controller._hand_worker_serial,
            feature_hand_observation(2, 10.19),
        )
    controller.stop()

    assert snapshots[-1].left is ProximityState.FAR
    near_snapshot = snapshots[-1]
    assert near_snapshot.right is ProximityState.NEAR
    assert events == []


def test_temple_tap_flows_through_controller_only_after_stable_release(qtbot: QtBot) -> None:
    del qtbot
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(temple_stabilization_ms=0),
        clock=FakeClock(1.0),
    )
    events: list[GestureEvent] = []
    controller.event_detected.connect(events.append)

    controller._publish_temple_feature(direct_temple_feature(1, 1.00, right_ratio=0.20))
    controller._publish_temple_feature(direct_temple_feature(2, 1.10, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(3, 1.11, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(4, 1.20, right_ratio=0.20))
    assert events == []

    controller._publish_temple_feature(direct_temple_feature(5, 1.21, right_ratio=0.20))

    assert [event.type for event in events] == [GestureEventType.RIGHT_TEMPLE_TAP]
    assert events[0].source_sequence == 5
    assert events[0].duration_ms == pytest.approx(90.0)


def test_temple_hold_start_and_release_end_flow_once_through_controller(
    qtbot: QtBot,
) -> None:
    del qtbot
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(
            temple_stabilization_ms=0,
            temple_hold_threshold_ms=100,
        ),
        clock=FakeClock(1.0),
    )
    events: list[GestureEvent] = []
    controller.event_detected.connect(events.append)

    controller._publish_temple_feature(direct_temple_feature(1, 1.00, right_ratio=0.20))
    controller._publish_temple_feature(direct_temple_feature(2, 1.10, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(3, 1.11, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(4, 1.21, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(5, 1.30, right_ratio=0.20))
    controller._publish_temple_feature(direct_temple_feature(6, 1.31, right_ratio=0.20))

    assert [event.type for event in events] == [
        GestureEventType.RIGHT_TEMPLE_HOLD_START,
        GestureEventType.RIGHT_TEMPLE_HOLD_END,
    ]


def test_temple_tracking_timeout_ends_hold_once_before_unknown_publication(
    qtbot: QtBot,
) -> None:
    del qtbot
    clock = FakeClock(1.0)
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(
            temple_stabilization_ms=0,
            temple_hold_threshold_ms=100,
        ),
        clock=clock,
    )
    events: list[GestureEvent] = []
    snapshots: list[TempleProximitySnapshot] = []
    trace: list[str] = []
    controller.event_detected.connect(events.append)
    controller.temple_proximity_changed.connect(snapshots.append)
    controller.event_detected.connect(lambda event: trace.append(event.type.value))
    controller.temple_proximity_changed.connect(
        lambda snapshot: trace.append(f"proximity:{snapshot.right.value}")
    )
    controller._enable_delivery()

    controller._publish_temple_feature(direct_temple_feature(1, 1.00, right_ratio=0.20))
    controller._publish_temple_feature(direct_temple_feature(2, 1.10, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(3, 1.11, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(4, 1.21, right_ratio=0.05))
    clock.now = 1.461
    trace.clear()

    controller.poll_timeouts()
    controller.poll_timeouts()

    assert [event.type for event in events] == [
        GestureEventType.RIGHT_TEMPLE_HOLD_START,
        GestureEventType.RIGHT_TEMPLE_HOLD_END,
    ]
    assert snapshots[-1].right is ProximityState.UNKNOWN
    assert trace == [
        GestureEventType.RIGHT_TEMPLE_HOLD_END.value,
        "proximity:unknown",
    ]
    controller.suspend()


def test_suspend_flushes_active_temple_hold_once(qtbot: QtBot) -> None:
    del qtbot
    clock = FakeClock(1.30)
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(
            temple_stabilization_ms=0,
            temple_hold_threshold_ms=100,
        ),
        clock=clock,
    )
    events: list[GestureEvent] = []
    controller.event_detected.connect(events.append)

    controller._publish_temple_feature(direct_temple_feature(1, 1.00, right_ratio=0.20))
    controller._publish_temple_feature(direct_temple_feature(2, 1.10, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(3, 1.11, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(4, 1.21, right_ratio=0.05))

    controller.suspend()
    controller.suspend()

    assert [event.type for event in events] == [
        GestureEventType.RIGHT_TEMPLE_HOLD_START,
        GestureEventType.RIGHT_TEMPLE_HOLD_END,
    ]


def test_reentrant_suspend_during_hold_start_defers_exactly_one_end(qtbot: QtBot) -> None:
    del qtbot
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(
            temple_stabilization_ms=0,
            temple_hold_threshold_ms=100,
        ),
        clock=FakeClock(1.30),
    )
    events: list[GestureEvent] = []

    def suspend_on_start(event: GestureEvent) -> None:
        events.append(event)
        if event.type is GestureEventType.RIGHT_TEMPLE_HOLD_START:
            controller.suspend()

    controller.event_detected.connect(suspend_on_start)
    controller._publish_temple_feature(direct_temple_feature(1, 1.00, right_ratio=0.20))
    controller._publish_temple_feature(direct_temple_feature(2, 1.10, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(3, 1.11, right_ratio=0.05))
    controller._publish_temple_feature(direct_temple_feature(4, 1.21, right_ratio=0.05))

    assert [event.type for event in events] == [
        GestureEventType.RIGHT_TEMPLE_HOLD_START,
        GestureEventType.RIGHT_TEMPLE_HOLD_END,
    ]
    assert controller._gesture_engine.temple_proximity_detector.snapshot.right is (
        ProximityState.UNKNOWN
    )


def test_reentrant_suspend_skips_unpublished_second_side_hold(qtbot: QtBot) -> None:
    del qtbot
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(
            temple_stabilization_ms=0,
            temple_hold_threshold_ms=100,
        ),
        clock=FakeClock(1.30),
    )
    events: list[GestureEvent] = []

    def suspend_on_left_start(event: GestureEvent) -> None:
        events.append(event)
        if event.type is GestureEventType.LEFT_TEMPLE_HOLD_START:
            controller.suspend()

    controller.event_detected.connect(suspend_on_left_start)
    controller._publish_temple_feature(
        direct_temple_feature(1, 1.00, left_ratio=0.20, right_ratio=0.20)
    )
    controller._publish_temple_feature(
        direct_temple_feature(2, 1.10, left_ratio=0.05, right_ratio=0.05)
    )
    controller._publish_temple_feature(
        direct_temple_feature(3, 1.11, left_ratio=0.05, right_ratio=0.05)
    )
    controller._publish_temple_feature(
        direct_temple_feature(4, 1.21, left_ratio=0.05, right_ratio=0.05)
    )

    assert [event.type for event in events] == [
        GestureEventType.LEFT_TEMPLE_HOLD_START,
        GestureEventType.LEFT_TEMPLE_HOLD_END,
    ]


def test_reentrant_suspend_from_raw_feature_cannot_repopulate_after_clear(
    qtbot: QtBot,
) -> None:
    del qtbot
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(temple_stabilization_ms=0),
        clock=FakeClock(1.0),
    )
    trace: list[str] = []
    controller.temple_proximity_changed.connect(lambda _snapshot: trace.append("proximity"))
    controller.temple_feature_changed.connect(lambda _feature: trace.append("raw"))
    controller.temple_feature_changed.connect(lambda _feature: controller.suspend())
    controller.temple_proximity_cleared.connect(lambda: trace.append("clear"))

    controller._publish_temple_feature(direct_temple_feature(1, 1.00, right_ratio=0.20))

    assert trace == ["proximity", "raw", "clear"]
    assert controller._gesture_engine.temple_proximity_detector.snapshot.right is (
        ProximityState.UNKNOWN
    )


def test_face_later_recompute_drives_proximity_without_new_hand_result(qtbot: QtBot) -> None:
    clock = FakeClock(10.0)
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        hand_backend_factory=FeatureHandBackend,
        clock=clock,
    )
    features: list[TempleFeatureObservation] = []
    snapshots: list[TempleProximitySnapshot] = []
    events: list[GestureEvent] = []
    controller.temple_feature_changed.connect(features.append)
    controller.temple_proximity_changed.connect(snapshots.append)
    controller.event_detected.connect(events.append)
    controller.start()
    controller._watchdog.stop()

    with qtbot.waitSignal(controller.temple_feature_changed, timeout=1000):
        controller._queue_hand_result(
            controller._hand_worker_serial,
            feature_hand_observation(1, 9.95, fingertip_x=0.5),
        )
    with qtbot.waitSignal(controller.temple_proximity_changed, timeout=1000):
        controller._queue_face_result(
            controller._face_worker_serial,
            feature_face_observation(1, 9.95),
        )
    controller.stop()

    assert [feature.status for feature in features] == [
        TempleFeatureStatus.FACE_UNAVAILABLE,
        TempleFeatureStatus.READY,
    ]
    assert snapshots[-1].left is ProximityState.FAR
    assert snapshots[-1].right is ProximityState.FAR
    assert events == []


def test_invalid_latest_feature_does_not_block_proximity_watchdog(qtbot: QtBot) -> None:
    clock = FakeClock(10.0)
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        hand_backend_factory=FeatureHandBackend,
        clock=clock,
    )
    features: list[TempleFeatureObservation] = []
    snapshots: list[TempleProximitySnapshot] = []
    events: list[GestureEvent] = []
    controller.temple_feature_changed.connect(features.append)
    controller.temple_proximity_changed.connect(snapshots.append)
    controller.event_detected.connect(events.append)
    controller.start()
    controller._watchdog.stop()

    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        controller._queue_face_result(
            controller._face_worker_serial,
            feature_face_observation(1, 10.0),
        )
    with qtbot.waitSignal(controller.temple_feature_changed, timeout=1000):
        controller._queue_hand_result(
            controller._hand_worker_serial,
            feature_hand_observation(1, 10.0),
        )
    clock.now = 10.19
    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        controller._queue_face_result(
            controller._face_worker_serial,
            feature_face_observation(2, 10.19),
        )
    with qtbot.waitSignal(controller.temple_proximity_changed, timeout=1000):
        controller._queue_hand_result(
            controller._hand_worker_serial,
            feature_hand_observation(2, 10.19),
        )
    near_snapshot = snapshots[-1]
    assert near_snapshot.right is ProximityState.NEAR

    clock.now = 10.20
    missing_face = FaceObservation(
        source_sequence=3,
        capture_timestamp=10.20,
        processed_timestamp=10.21,
        face_detected=False,
    )
    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        controller._queue_face_result(controller._face_worker_serial, missing_face)
    with qtbot.waitSignal(controller.temple_feature_changed, timeout=1000):
        controller._queue_hand_result(
            controller._hand_worker_serial,
            feature_hand_observation(3, 10.20),
        )
    assert features[-1].status is TempleFeatureStatus.FACE_NOT_DETECTED

    clock.now = 10.45
    with qtbot.waitSignal(controller.temple_proximity_changed, timeout=1000):
        controller.poll_timeouts()
    controller.stop()

    assert features[-1].status is TempleFeatureStatus.FACE_NOT_DETECTED
    expired_snapshot = snapshots[-1]
    assert expired_snapshot.left is ProximityState.UNKNOWN
    assert expired_snapshot.right is ProximityState.UNKNOWN
    assert events == []


def test_stale_face_resets_wink_state_without_silently_resetting_temple(
    qtbot: QtBot,
) -> None:
    clock = FakeClock(10.0)
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        hand_backend_factory=FeatureHandBackend,
        clock=clock,
    )
    snapshots: list[TempleProximitySnapshot] = []
    events: list[GestureEvent] = []
    controller.temple_proximity_changed.connect(snapshots.append)
    controller.event_detected.connect(events.append)
    controller.start()
    controller._watchdog.stop()

    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        controller._queue_face_result(
            controller._face_worker_serial,
            feature_face_observation(1, 10.0),
        )
    with qtbot.waitSignal(controller.temple_proximity_changed, timeout=1000):
        controller._queue_hand_result(
            controller._hand_worker_serial,
            feature_hand_observation(1, 10.0, fingertip_x=0.5),
        )
    assert snapshots[-1].right is ProximityState.FAR

    clock.now = 10.10
    with qtbot.waitSignal(controller.observation_cleared, timeout=1000):
        controller._queue_face_result(
            controller._face_worker_serial,
            feature_face_observation(2, 9.80),
        )

    assert controller._gesture_engine.temple_proximity_detector.snapshot.right is (
        ProximityState.FAR
    )
    assert len(snapshots) == 1
    assert events == []
    controller.stop()


def test_suspend_clears_derived_temple_proximity(qtbot: QtBot) -> None:
    clock = FakeClock(10.0)
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        hand_backend_factory=FeatureHandBackend,
        clock=clock,
    )
    snapshots: list[TempleProximitySnapshot] = []
    events: list[GestureEvent] = []
    clears: list[str] = []
    controller.temple_proximity_changed.connect(snapshots.append)
    controller.temple_proximity_cleared.connect(lambda: clears.append("temple"))
    controller.cheek_proximity_cleared.connect(lambda: clears.append("cheek"))
    controller.event_detected.connect(events.append)
    controller.start()
    controller._watchdog.stop()

    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        controller._queue_face_result(
            controller._face_worker_serial,
            feature_face_observation(1, 10.0),
        )
    with qtbot.waitSignal(controller.temple_proximity_changed, timeout=1000):
        controller._queue_hand_result(
            controller._hand_worker_serial,
            feature_hand_observation(1, 10.0, fingertip_x=0.5),
        )
    with qtbot.waitSignal(controller.cheek_proximity_cleared, timeout=1000):
        controller.suspend()

    assert snapshots[-1].right is ProximityState.FAR
    assert controller._gesture_engine.temple_proximity_detector.snapshot.right is (
        ProximityState.UNKNOWN
    )
    assert controller._gesture_engine.cheek_proximity_detector.snapshot.right is (
        ProximityState.UNKNOWN
    )
    assert clears == ["temple", "cheek"]
    assert events == []
    controller.stop()


def test_old_generation_marker_drops_stale_result_without_losing_current(
    qtbot: QtBot,
) -> None:
    frames = LatestFrameBuffer()
    controller = VisionController(
        frames,
        lambda: FeatureFaceBackend(),
        GestureSettings(),
        clock=FakeClock(1.0),
    )
    observations: list[FaceObservation] = []
    controller.observation_changed.connect(observations.append)
    controller.start()
    old_serial = controller._face_worker_serial
    stale = FaceObservation(
        source_sequence=99,
        capture_timestamp=1.0,
        processed_timestamp=1.01,
        face_detected=True,
    )

    controller._queue_face_result(old_serial, stale)
    controller.suspend()
    controller.start()
    current = FaceObservation(
        source_sequence=1,
        capture_timestamp=1.0,
        processed_timestamp=1.01,
        face_detected=True,
    )
    controller._queue_face_result(controller._face_worker_serial, current)
    qtbot.waitUntil(lambda: len(observations) == 1, timeout=1000)
    controller.stop()

    assert [item.source_sequence for item in observations] == [1]


def test_fresh_face_publishes_binocular_gaze_and_watchdog_expires_it(qtbot: QtBot) -> None:
    clock = FakeClock(10.0)
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        clock=clock,
    )
    features: list[GazeFeatureObservation] = []
    controller.gaze_feature_changed.connect(features.append)
    controller.start()

    with qtbot.waitSignal(controller.gaze_feature_changed, timeout=1000):
        controller._queue_face_result(
            controller._face_worker_serial,
            feature_face_observation(1, 9.95),
        )
    clock.now = 10.201
    with qtbot.waitSignal(controller.gaze_feature_cleared, timeout=1000):
        controller.poll_timeouts()
    controller.stop()

    assert len(features) == 1
    assert features[0].status is GazeFeatureStatus.READY
    assert features[0].combined is not None
    assert features[0].combined.horizontal == pytest.approx(0.5)
    assert features[0].combined.vertical == pytest.approx(0.5)


def test_suspend_clears_gaze_and_old_generation_cannot_repopulate(qtbot: QtBot) -> None:
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        clock=FakeClock(10.0),
    )
    features: list[GazeFeatureObservation] = []
    controller.gaze_feature_changed.connect(features.append)
    controller.start()
    serial = controller._face_worker_serial

    with qtbot.waitSignal(controller.gaze_feature_changed, timeout=1000):
        controller._queue_face_result(serial, feature_face_observation(1, 9.95))
    with qtbot.waitSignal(controller.gaze_feature_cleared, timeout=1000):
        controller.suspend()
    controller._queue_face_result(serial, feature_face_observation(2, 9.96))
    qtbot.wait(20)
    controller.stop()

    assert [feature.source_sequence for feature in features] == [1]


def test_gaze_feature_qt_boundary_rejects_wrong_payload() -> None:
    feature = GazeFeatureObservation(
        source_sequence=1,
        capture_timestamp=1.0,
        processed_timestamp=1.01,
        status=GazeFeatureStatus.FACE_NOT_DETECTED,
    )

    assert gaze_feature_observation(feature) is feature
    with pytest.raises(TypeError, match="Expected GazeFeatureObservation"):
        gaze_feature_observation(object())


def test_hand_first_same_frame_is_recomputed_when_face_finishes(qtbot: QtBot) -> None:
    frames = LatestFrameBuffer()
    face_backend = SlowFeatureFaceBackend()
    hand_backend = FeatureHandBackend()
    controller = VisionController(
        frames,
        lambda: face_backend,
        GestureSettings(),
        hand_backend_factory=lambda: hand_backend,
        hand_target_fps=50.0,
        clock=FakeClock(10.0),
    )
    features: list[TempleFeatureObservation] = []
    controller.temple_feature_changed.connect(features.append)
    controller.start()

    frames.publish(np.zeros((480, 640, 3), dtype=np.uint8), 9.95)
    qtbot.waitUntil(
        lambda: any(feature.status is TempleFeatureStatus.FACE_UNAVAILABLE for feature in features),
        timeout=1000,
    )
    qtbot.waitUntil(
        lambda: any(feature.status is TempleFeatureStatus.READY for feature in features),
        timeout=1000,
    )
    controller.stop()

    assert [feature.status for feature in features] == [
        TempleFeatureStatus.FACE_UNAVAILABLE,
        TempleFeatureStatus.READY,
    ]


def test_result_backlog_coalesces_each_worker_to_its_latest_observation(
    qtbot: QtBot,
) -> None:
    frames = LatestFrameBuffer()
    controller = VisionController(
        frames,
        FeatureFaceBackend,
        GestureSettings(),
        hand_backend_factory=FeatureHandBackend,
        clock=FakeClock(10.0),
    )
    faces: list[FaceObservation] = []
    hands: list[HandObservation] = []
    controller.observation_changed.connect(faces.append)
    controller.hand_observation_changed.connect(hands.append)
    controller.start()

    controller._queue_face_result(
        controller._face_worker_serial,
        feature_face_observation(1, 9.90),
    )
    controller._queue_face_result(
        controller._face_worker_serial,
        feature_face_observation(2, 9.95),
    )
    controller._queue_hand_result(
        controller._hand_worker_serial,
        feature_hand_observation(1, 9.90),
    )
    controller._queue_hand_result(
        controller._hand_worker_serial,
        feature_hand_observation(2, 9.95),
    )
    qtbot.waitUntil(lambda: len(faces) == 1 and len(hands) == 1, timeout=1000)
    controller.stop()

    assert [item.source_sequence for item in faces] == [2]
    assert [item.source_sequence for item in hands] == [2]


def test_stale_queued_wink_sample_clears_candidate_without_event(qtbot: QtBot) -> None:
    frames = LatestFrameBuffer()
    clock = FakeClock(1.0)
    controller = VisionController(
        frames,
        lambda: SequencedFaceBackend({}),
        GestureSettings(),
        clock=clock,
    )
    events: list[GestureEvent] = []
    observations: list[FaceObservation] = []
    controller.event_detected.connect(events.append)
    controller.observation_changed.connect(observations.append)
    controller.start()
    serial = controller._face_worker_serial

    open_face = FaceObservation(1, 1.00, 1.01, True, left_eye_openness=0.9, right_eye_openness=0.9)
    closed_candidate = FaceObservation(
        2,
        1.05,
        1.06,
        True,
        left_eye_openness=0.2,
        right_eye_openness=0.9,
    )
    would_emit_if_fresh = FaceObservation(
        3,
        1.20,
        1.21,
        True,
        left_eye_openness=0.2,
        right_eye_openness=0.9,
    )
    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        controller._queue_face_result(serial, open_face)
    clock.now = 1.05
    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        controller._queue_face_result(serial, closed_candidate)
    clock.now = 1.451
    with qtbot.waitSignal(controller.observation_cleared, timeout=1000):
        controller._queue_face_result(serial, would_emit_if_fresh)
    controller.stop()

    assert [item.source_sequence for item in observations] == [1, 2]
    assert events == []


def test_running_health_cannot_repopulate_after_suspend_but_terminal_health_can(
    qtbot: QtBot,
) -> None:
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        clock=FakeClock(1.0),
    )
    health_updates: list[VisionHealth] = []
    controller.health_changed.connect(health_updates.append)
    controller.start()
    qtbot.waitUntil(lambda: controller.status is VisionStatus.RUNNING, timeout=1000)
    serial = controller._face_worker_serial
    controller.suspend()
    health_updates.clear()

    controller._queue_face_health(
        serial,
        VisionHealth(
            status=VisionStatus.RUNNING,
            message="stale running sentinel",
            face_detected=True,
        ),
    )
    terminal = VisionHealth(
        status=VisionStatus.STOPPING,
        message="terminal sentinel",
    )
    with qtbot.waitSignal(controller.health_changed, timeout=1000):
        controller._queue_face_health(serial, terminal)
    controller.stop()

    assert all(item.message != "stale running sentinel" for item in health_updates)
    assert terminal in health_updates


def test_health_backlog_coalesces_to_latest_face_and_hand_state(qtbot: QtBot) -> None:
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        hand_backend_factory=FeatureHandBackend,
        clock=FakeClock(1.0),
    )
    face_health: list[VisionHealth] = []
    hand_health: list[HandVisionHealth] = []
    controller.health_changed.connect(face_health.append)
    controller.hand_health_changed.connect(hand_health.append)
    controller.start()
    qtbot.waitUntil(
        lambda: (
            controller.status is VisionStatus.RUNNING
            and controller.hand_status is VisionStatus.RUNNING
        ),
        timeout=1000,
    )
    qtbot.wait(30)
    face_health.clear()
    hand_health.clear()

    controller._queue_face_health(
        controller._face_worker_serial,
        VisionHealth(status=VisionStatus.RUNNING, message="queued face first"),
    )
    controller._queue_face_health(
        controller._face_worker_serial,
        VisionHealth(status=VisionStatus.RUNNING, message="queued face latest"),
    )
    controller._queue_hand_health(
        controller._hand_worker_serial,
        HandVisionHealth(status=VisionStatus.RUNNING, message="queued hand first"),
    )
    controller._queue_hand_health(
        controller._hand_worker_serial,
        HandVisionHealth(status=VisionStatus.RUNNING, message="queued hand latest"),
    )
    qtbot.waitUntil(
        lambda: (
            any(item.message == "queued face latest" for item in face_health)
            and any(item.message == "queued hand latest" for item in hand_health)
        ),
        timeout=1000,
    )
    controller.stop()

    queued_face = [item.message for item in face_health if item.message.startswith("queued")]
    queued_hand = [item.message for item in hand_health if item.message.startswith("queued")]
    assert queued_face == ["queued face latest"]
    assert queued_hand == ["queued hand latest"]


def test_fresh_face_recomputes_cached_stale_hand_as_explicitly_stale(qtbot: QtBot) -> None:
    clock = FakeClock(10.0)
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        hand_backend_factory=FeatureHandBackend,
        clock=clock,
    )
    features: list[TempleFeatureObservation] = []
    controller.temple_feature_changed.connect(features.append)
    controller.start()

    with qtbot.waitSignal(controller.temple_feature_changed, timeout=1000):
        controller._queue_hand_result(
            controller._hand_worker_serial,
            feature_hand_observation(1, 9.95),
        )
    clock.now = 10.30
    with qtbot.waitSignal(controller.temple_feature_changed, timeout=1000):
        controller._queue_face_result(
            controller._face_worker_serial,
            feature_face_observation(2, 10.29),
        )
    controller.stop()

    assert [item.status for item in features] == [
        TempleFeatureStatus.FACE_UNAVAILABLE,
        TempleFeatureStatus.HAND_STALE,
    ]


def test_hand_stop_is_attempted_when_face_worker_times_out(qtbot: QtBot) -> None:
    controller = VisionController(
        LatestFrameBuffer(),
        FeatureFaceBackend,
        GestureSettings(),
        hand_backend_factory=FeatureHandBackend,
    )
    face = StopStub(
        VisionHealth(status=VisionStatus.RUNNING, message="face running"),
        fail=True,
    )
    hand = StopStub(
        HandVisionHealth(status=VisionStatus.RUNNING, message="hand running"),
        fail=False,
    )
    face_health: list[VisionHealth] = []
    controller.health_changed.connect(face_health.append)
    controller._face_worker = cast(Any, face)
    controller._hand_worker = cast(Any, hand)

    controller.stop()
    qtbot.waitUntil(
        lambda: any(item.status is VisionStatus.ERROR for item in face_health),
        timeout=1000,
    )

    assert face.stop_called
    assert hand.stop_called
    assert hand.invalidated
    assert controller._face_worker is not None
    assert controller._hand_worker is None
