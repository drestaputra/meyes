"""Qt vision/gesture orchestration tests in no-input safe mode."""

from __future__ import annotations

import threading
import time
from typing import Any, cast

import numpy as np
from pytestqt.qtbot import QtBot

from meyes.camera.buffer import LatestFrameBuffer
from meyes.camera.models import FramePacket
from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import (
    DetectedHand,
    FaceObservation,
    HandObservation,
    HandSide,
    NormalizedPoint,
    TempleFeatureObservation,
    TempleFeatureStatus,
)
from meyes.gestures.temple_proximity import ProximityState, TempleProximitySnapshot
from meyes.vision.controller import VisionController
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
        height, width = packet.frame.shape[:2]
        return FaceObservation(
            source_sequence=packet.sequence,
            capture_timestamp=packet.capture_timestamp,
            processed_timestamp=packet.capture_timestamp + 0.01,
            face_detected=True,
            left_eye_openness=0.9,
            right_eye_openness=0.9,
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
    with qtbot.waitSignal(controller.temple_proximity_cleared, timeout=1000):
        controller.suspend()

    assert snapshots[-1].right is ProximityState.FAR
    assert controller._gesture_engine.temple_proximity_detector.snapshot.right is (
        ProximityState.UNKNOWN
    )
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
