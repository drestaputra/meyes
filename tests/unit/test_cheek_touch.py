"""Release-triggered cheek-touch gesture tests."""

from __future__ import annotations

import pytest

from meyes.domain.events import GestureEventType
from meyes.domain.observations import (
    HandSide,
    TempleFeatureObservation,
    TempleFeatureStatus,
    TempleProximity,
)
from meyes.gestures.cheek_touch import (
    CheekTouchDetector,
    CheekTouchSettings,
    CheekTouchState,
)
from meyes.gestures.engine import GestureEngine
from meyes.gestures.temple_proximity import (
    ProximitySource,
    ProximityState,
    TempleProximityDetector,
    TempleProximitySettings,
    TempleProximitySnapshot,
)


def snapshot(
    sequence: int,
    timestamp: float,
    *,
    left: ProximityState = ProximityState.FAR,
    right: ProximityState = ProximityState.FAR,
    left_release_started_at: float | None = None,
    right_release_started_at: float | None = None,
) -> TempleProximitySnapshot:
    return TempleProximitySnapshot(
        sequence,
        timestamp,
        left,
        right,
        left_release_started_at=left_release_started_at,
        right_release_started_at=right_release_started_at,
    )


def feature(sequence: int, timestamp: float, *, right_cheek: float) -> TempleFeatureObservation:
    return TempleFeatureObservation(
        source_sequence=sequence,
        capture_timestamp=timestamp,
        processed_timestamp=timestamp,
        status=TempleFeatureStatus.READY,
        cheek_proximities=(TempleProximity(HandSide.RIGHT, right_cheek, 0.9),),
    )


def test_touch_emits_once_on_release_and_requires_far_rearm() -> None:
    detector = CheekTouchDetector(CheekTouchSettings(cooldown=0.1))

    assert detector.update(snapshot(1, 1.0)) == ()
    assert detector.update(snapshot(2, 1.1, right=ProximityState.NEAR)) == ()
    assert detector.update(snapshot(3, 1.2, right=ProximityState.NEAR)) == ()
    released = detector.update(
        snapshot(
            4,
            1.3,
            right=ProximityState.FAR,
            right_release_started_at=1.25,
        )
    )

    assert [event.type for event in released] == [GestureEventType.RIGHT_CHEEK_TOUCH]
    assert released[0].duration_ms == pytest.approx(150.0)
    assert detector.update(snapshot(5, 1.35, right=ProximityState.NEAR)) == ()
    assert detector.update(snapshot(6, 1.41)) == ()
    assert detector.debug_state.right is CheekTouchState.IDLE


def test_tracking_loss_during_touch_never_clicks() -> None:
    detector = CheekTouchDetector()
    detector.update(snapshot(1, 1.0))
    detector.update(snapshot(2, 1.1, left=ProximityState.NEAR))

    assert detector.update(snapshot(3, 1.2, left=ProximityState.UNKNOWN)) == ()
    assert detector.update(snapshot(4, 1.3)) == ()
    assert detector.debug_state.left is CheekTouchState.IDLE


def test_left_cheek_touch_emits_its_distinct_event() -> None:
    detector = CheekTouchDetector(CheekTouchSettings(cooldown=0))

    detector.update(snapshot(1, 1.0))
    detector.update(snapshot(2, 1.1, left=ProximityState.NEAR))
    released = detector.update(
        snapshot(
            3,
            1.2,
            left=ProximityState.FAR,
            left_release_started_at=1.18,
        )
    )

    assert [event.type for event in released] == [GestureEventType.LEFT_CHEEK_TOUCH]


def test_gesture_engine_emits_right_cheek_touch_from_face_hand_features() -> None:
    settings = TempleProximitySettings(stabilization=0)
    engine = GestureEngine(
        cheek_proximity_detector=TempleProximityDetector(
            settings,
            source=ProximitySource.CHEEK,
        ),
        cheek_touch_detector=CheekTouchDetector(CheekTouchSettings(cooldown=0)),
    )

    results = (
        engine.update_temple(feature(1, 1.00, right_cheek=0.20)),
        engine.update_temple(feature(2, 1.01, right_cheek=0.05)),
        engine.update_temple(feature(3, 1.02, right_cheek=0.05)),
        engine.update_temple(feature(4, 1.03, right_cheek=0.20)),
        engine.update_temple(feature(5, 1.04, right_cheek=0.20)),
    )

    events = tuple(event for result in results for event in result.events)
    assert [event.type for event in events] == [GestureEventType.RIGHT_CHEEK_TOUCH]
    assert results[2].cheek_proximity is not None
    assert results[2].cheek_proximity.right is ProximityState.NEAR
    assert results[4].cheek_proximity is not None
    assert results[4].cheek_proximity.right is ProximityState.FAR
