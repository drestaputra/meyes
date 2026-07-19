"""Deterministic semantic tap/hold tests over stable temple states."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TypedDict, cast

import pytest

from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import (
    HandSide,
    TempleFeatureObservation,
    TempleFeatureStatus,
    TempleProximity,
)
from meyes.gestures.engine import GestureEngine
from meyes.gestures.temple_gestures import (
    TempleGestureDetector as ProductionTempleGestureDetector,
)
from meyes.gestures.temple_gestures import (
    TempleGestureSettings,
    TempleInteractionState,
)
from meyes.gestures.temple_proximity import ProximityState, TempleProximitySnapshot

FIXTURES = Path(__file__).parents[1] / "fixtures" / "observation_sequences"


class TempleSample(TypedDict):
    t_ms: int
    left: str
    right: str


class TempleGestureDetector(ProductionTempleGestureDetector):
    """Test adapter that makes synthetic snapshot arrival equal capture by default."""

    def update(
        self,
        snapshot: TempleProximitySnapshot,
        *,
        current_timestamp: float | None = None,
    ) -> tuple[GestureEvent, ...]:
        arrival = snapshot.timestamp if current_timestamp is None else current_timestamp
        assert arrival is not None
        return super().update(snapshot, current_timestamp=arrival)


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
        left_release_started_at,
        right_release_started_at,
    )


def feature(
    sequence: int,
    timestamp: float,
    *,
    right: float,
    processed_timestamp: float | None = None,
    status: TempleFeatureStatus = TempleFeatureStatus.READY,
) -> TempleFeatureObservation:
    return TempleFeatureObservation(
        source_sequence=sequence,
        capture_timestamp=timestamp,
        processed_timestamp=(
            timestamp + 0.001 if processed_timestamp is None else processed_timestamp
        ),
        status=status,
        proximities=(TempleProximity(HandSide.RIGHT, right, 0.9),),
    )


def event_types(events: tuple[GestureEvent, ...]) -> list[GestureEventType]:
    return [event.type for event in events]


def arm(detector: TempleGestureDetector, timestamp: float = 0.0) -> None:
    assert detector.update(snapshot(1, timestamp)) == ()


def run_fixture(name: str) -> list[GestureEvent]:
    samples = cast(
        list[TempleSample],
        json.loads((FIXTURES / name).read_text(encoding="utf-8")),
    )
    detector = TempleGestureDetector()
    events: list[GestureEvent] = []
    for sequence, sample in enumerate(samples, start=1):
        events.extend(
            detector.update(
                snapshot(
                    sequence,
                    sample["t_ms"] / 1000.0,
                    left=ProximityState(sample["left"]),
                    right=ProximityState(sample["right"]),
                )
            )
        )
    return events


def test_defaults_convert_from_persisted_millisecond_settings() -> None:
    settings = TempleGestureSettings.from_settings(GestureSettings())

    assert settings == TempleGestureSettings(hold_threshold=0.550, cooldown=0.250)


def test_gesture_engine_converts_persisted_temple_semantic_timing() -> None:
    engine = GestureEngine.from_settings(
        GestureSettings(
            temple_hold_threshold_ms=700,
            temple_cooldown_ms=400,
        )
    )

    assert engine.temple_gesture_detector.settings == TempleGestureSettings(
        hold_threshold=0.700,
        cooldown=0.400,
    )


def test_recorded_right_temple_tap_fixture_emits_on_release() -> None:
    events = run_fixture("right_temple_tap.json")

    assert event_types(tuple(events)) == [GestureEventType.RIGHT_TEMPLE_TAP]


def test_recorded_left_temple_hold_fixture_emits_one_start_and_end() -> None:
    events = run_fixture("left_temple_hold.json")

    assert event_types(tuple(events)) == [
        GestureEventType.LEFT_TEMPLE_HOLD_START,
        GestureEventType.LEFT_TEMPLE_HOLD_END,
    ]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"hold_threshold": 0.0}, "positive"),
        ({"hold_threshold": math.nan}, "finite"),
        ({"cooldown": -0.1}, "non-negative"),
        ({"cooldown": math.inf}, "finite"),
    ],
)
def test_settings_reject_invalid_values(
    kwargs: dict[str, float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        TempleGestureSettings(**kwargs)


def test_initial_near_is_disarmed_until_far_then_reentry() -> None:
    detector = TempleGestureDetector()

    assert detector.update(snapshot(1, 0.00, right=ProximityState.NEAR)) == ()
    assert detector.update(snapshot(2, 0.60, right=ProximityState.NEAR)) == ()
    assert detector.update(snapshot(3, 0.70)) == ()
    assert detector.update(snapshot(4, 0.80, right=ProximityState.NEAR)) == ()
    events = detector.update(snapshot(5, 1.00))

    assert event_types(events) == [GestureEventType.RIGHT_TEMPLE_TAP]
    assert events[0].duration_ms == pytest.approx(200.0)


def test_tap_is_emitted_only_after_confirmed_release() -> None:
    detector = TempleGestureDetector()
    arm(detector)

    assert detector.update(snapshot(2, 0.10, left=ProximityState.NEAR)) == ()
    assert detector.update(snapshot(3, 0.40, left=ProximityState.NEAR)) == ()
    events = detector.update(snapshot(4, 0.50))

    assert event_types(events) == [GestureEventType.LEFT_TEMPLE_TAP]
    assert events[0].source_sequence == 4
    assert events[0].timestamp == 0.50
    assert events[0].duration_ms == pytest.approx(400.0)


def test_hold_start_at_boundary_emits_once_and_release_ends_once() -> None:
    detector = TempleGestureDetector()
    arm(detector)
    detector.update(snapshot(2, 0.10, right=ProximityState.NEAR))

    started = detector.update(snapshot(3, 0.65, right=ProximityState.NEAR))
    repeated = detector.update(snapshot(4, 0.80, right=ProximityState.NEAR))
    ended = detector.update(snapshot(5, 0.90))

    assert event_types(started) == [GestureEventType.RIGHT_TEMPLE_HOLD_START]
    assert started[0].duration_ms == pytest.approx(550.0)
    assert repeated == ()
    assert event_types(ended) == [GestureEventType.RIGHT_TEMPLE_HOLD_END]
    assert ended[0].duration_ms == pytest.approx(800.0)


def test_coarse_release_at_hold_boundary_emits_start_then_end_not_tap() -> None:
    detector = TempleGestureDetector()
    arm(detector)
    detector.update(snapshot(2, 0.10, left=ProximityState.NEAR))

    events = detector.update(snapshot(3, 0.65))

    assert event_types(events) == [
        GestureEventType.LEFT_TEMPLE_HOLD_START,
        GestureEventType.LEFT_TEMPLE_HOLD_END,
    ]
    assert [event.duration_ms for event in events] == pytest.approx([550.0, 550.0])


def test_release_candidate_before_hold_threshold_blocks_promotion_and_taps() -> None:
    detector = TempleGestureDetector()
    arm(detector)
    detector.update(snapshot(2, 0.281, right=ProximityState.NEAR))

    assert (
        detector.update(
            snapshot(
                3,
                0.84,
                right=ProximityState.NEAR,
                right_release_started_at=0.80,
            )
        )
        == ()
    )
    released = detector.update(
        snapshot(
            4,
            0.981,
            right=ProximityState.FAR,
            right_release_started_at=0.80,
        )
    )

    assert event_types(released) == [GestureEventType.RIGHT_TEMPLE_TAP]
    assert released[0].timestamp == 0.981
    assert released[0].duration_ms == pytest.approx(519.0)


def test_release_candidate_before_press_is_rejected_atomically() -> None:
    detector = TempleGestureDetector()
    arm(detector)
    detector.update(snapshot(2, 0.10, left=ProximityState.NEAR))

    malformed = detector.update(
        snapshot(
            3,
            0.20,
            left=ProximityState.FAR,
            left_release_started_at=0.05,
        )
    )
    released = detector.update(
        snapshot(
            3,
            0.25,
            left=ProximityState.FAR,
            left_release_started_at=0.20,
        )
    )

    assert malformed == ()
    assert event_types(released) == [GestureEventType.LEFT_TEMPLE_TAP]
    assert released[0].duration_ms == pytest.approx(100.0)


def test_tracking_loss_before_hold_cancels_without_tap_or_start() -> None:
    detector = TempleGestureDetector()
    arm(detector)
    detector.update(snapshot(2, 0.10, left=ProximityState.NEAR))

    assert detector.expire(0.40) == ()
    assert detector.debug_state.left is TempleInteractionState.WAITING_FOR_FAR
    assert detector.update(snapshot(3, 0.41, left=ProximityState.NEAR)) == ()


def test_tracking_loss_after_hold_emits_one_end_and_never_a_tap() -> None:
    detector = TempleGestureDetector()
    arm(detector)
    detector.update(snapshot(2, 0.10, left=ProximityState.NEAR))
    detector.update(snapshot(3, 0.65, left=ProximityState.NEAR))

    ended = detector.expire(0.90)
    duplicate = detector.expire(0.90)

    assert event_types(ended) == [GestureEventType.LEFT_TEMPLE_HOLD_END]
    assert ended[0].source_sequence == 3
    assert duplicate == ()


def test_reset_ends_each_active_hold_once_and_accepts_restarted_ordering() -> None:
    detector = TempleGestureDetector(TempleGestureSettings(hold_threshold=0.2))
    arm(detector)
    detector.update(
        snapshot(
            2,
            0.10,
            left=ProximityState.NEAR,
            right=ProximityState.NEAR,
        )
    )
    detector.update(
        snapshot(
            3,
            0.30,
            left=ProximityState.NEAR,
            right=ProximityState.NEAR,
        )
    )

    ended = detector.reset(0.40)
    duplicate = detector.reset(0.50)

    assert event_types(ended) == [
        GestureEventType.LEFT_TEMPLE_HOLD_END,
        GestureEventType.RIGHT_TEMPLE_HOLD_END,
    ]
    assert duplicate == ()
    assert detector.update(snapshot(1, 0.0)) == ()


def test_unknown_at_hold_threshold_does_not_infer_a_hold() -> None:
    detector = TempleGestureDetector()
    arm(detector)
    detector.update(snapshot(2, 0.10, right=ProximityState.NEAR))

    assert detector.expire(0.65) == ()


def test_cooldown_does_not_queue_near_and_requires_far_after_deadline() -> None:
    detector = TempleGestureDetector()
    arm(detector)
    detector.update(snapshot(2, 0.10, right=ProximityState.NEAR))
    assert event_types(detector.update(snapshot(3, 0.20))) == [GestureEventType.RIGHT_TEMPLE_TAP]

    assert detector.update(snapshot(4, 0.50, right=ProximityState.NEAR)) == ()
    assert detector.update(snapshot(5, 0.60, right=ProximityState.NEAR)) == ()
    assert detector.update(snapshot(6, 0.70)) == ()
    assert detector.update(snapshot(7, 0.80, right=ProximityState.NEAR)) == ()
    second = detector.update(snapshot(8, 0.90))

    assert event_types(second) == [GestureEventType.RIGHT_TEMPLE_TAP]


def test_sides_are_independent_with_deterministic_left_then_right_order() -> None:
    detector = TempleGestureDetector()
    arm(detector)
    detector.update(
        snapshot(
            2,
            0.10,
            left=ProximityState.NEAR,
            right=ProximityState.NEAR,
        )
    )

    starts = detector.update(
        snapshot(
            3,
            0.65,
            left=ProximityState.NEAR,
            right=ProximityState.NEAR,
        )
    )
    ends = detector.update(snapshot(4, 0.75))

    assert event_types(starts) == [
        GestureEventType.LEFT_TEMPLE_HOLD_START,
        GestureEventType.RIGHT_TEMPLE_HOLD_START,
    ]
    assert event_types(ends) == [
        GestureEventType.LEFT_TEMPLE_HOLD_END,
        GestureEventType.RIGHT_TEMPLE_HOLD_END,
    ]


def test_future_duplicate_and_regressing_evidence_cannot_advance_dwell() -> None:
    detector = TempleGestureDetector()
    arm(detector, 1.0)
    detector.update(snapshot(2, 1.10, left=ProximityState.NEAR))

    assert (
        detector.update(snapshot(3, 1.65, left=ProximityState.NEAR), current_timestamp=1.20) == ()
    )
    assert detector.update(snapshot(2, 1.10, left=ProximityState.NEAR)) == ()
    assert detector.update(snapshot(2, 1.20, left=ProximityState.NEAR)) == ()
    assert detector.update(snapshot(1, 1.20, left=ProximityState.NEAR)) == ()
    released = detector.update(snapshot(3, 1.30))

    assert event_types(released) == [GestureEventType.LEFT_TEMPLE_TAP]
    assert released[0].duration_ms == pytest.approx(200.0)


def test_malformed_snapshot_is_rejected_atomically() -> None:
    detector = TempleGestureDetector()
    arm(detector)
    malformed = TempleProximitySnapshot(
        2,
        0.10,
        cast(ProximityState, "near"),
        ProximityState.FAR,
    )

    assert detector.update(malformed) == ()
    assert detector.debug_state.left is TempleInteractionState.IDLE


def test_evidence_captured_before_expiry_cannot_reenter_after_expiry() -> None:
    detector = TempleGestureDetector()
    arm(detector, 10.0)
    detector.update(snapshot(2, 10.10, left=ProximityState.NEAR))
    detector.expire(10.30)

    assert detector.update(snapshot(3, 10.20)) == ()
    assert detector.debug_state.left.value == TempleInteractionState.WAITING_FOR_FAR.value
    assert detector.update(snapshot(4, 10.31)) == ()
    assert detector.debug_state.left.value == TempleInteractionState.IDLE.value


def test_regressing_arrival_time_cannot_release_or_create_an_event() -> None:
    detector = TempleGestureDetector()
    assert detector.update(snapshot(1, 1.00), current_timestamp=10.0) == ()
    assert (
        detector.update(
            snapshot(2, 1.10, left=ProximityState.NEAR),
            current_timestamp=11.0,
        )
        == ()
    )

    assert detector.update(snapshot(3, 1.20), current_timestamp=2.0) == ()
    released = detector.update(snapshot(3, 1.20), current_timestamp=11.1)

    assert event_types(released) == [GestureEventType.LEFT_TEMPLE_TAP]


def test_malformed_timestamp_and_arrival_types_fail_closed() -> None:
    detector = TempleGestureDetector()
    malformed_timestamp = TempleProximitySnapshot(
        1,
        cast(float, "bad"),
        ProximityState.FAR,
        ProximityState.FAR,
    )

    assert detector.update(malformed_timestamp, current_timestamp=1.0) == ()
    assert (
        detector.update(
            snapshot(1, 1.0),
            current_timestamp=cast(float, object()),
        )
        == ()
    )
    assert (
        detector.update(
            snapshot(1, cast(float, 10**1000)),
            current_timestamp=cast(float, 10**1000),
        )
        == ()
    )


def test_engine_watchdog_does_not_promote_pressed_without_new_evidence() -> None:
    engine = GestureEngine.from_settings(
        GestureSettings(
            temple_stabilization_ms=0,
            temple_hold_threshold_ms=100,
        )
    )
    engine.update_temple(feature(1, 0.00, right=0.20))
    engine.update_temple(feature(2, 0.10, right=0.05))
    engine.update_temple(feature(3, 0.11, right=0.05))

    assert engine.poll_temple(0.21).events == ()
    started = engine.update_temple(feature(4, 0.22, right=0.05))

    assert event_types(started.events) == [GestureEventType.RIGHT_TEMPLE_HOLD_START]


def test_engine_uses_raw_release_onset_before_stable_far_to_preserve_tap() -> None:
    engine = GestureEngine.from_settings(GestureSettings())
    results = [
        engine.update_temple(feature(1, 0.000, right=0.20)),
        engine.update_temple(feature(2, 0.100, right=0.05)),
        engine.update_temple(feature(3, 0.281, right=0.05)),
        engine.update_temple(feature(4, 0.500, right=0.05)),
        engine.update_temple(feature(5, 0.700, right=0.05)),
        engine.update_temple(feature(6, 0.800, right=0.20)),
        engine.update_temple(feature(7, 0.840, right=0.20)),
        engine.update_temple(feature(8, 0.981, right=0.20)),
    ]

    assert [event.type for result in results for event in result.events] == [
        GestureEventType.RIGHT_TEMPLE_TAP
    ]
    assert results[-1].events[0].duration_ms == pytest.approx(519.0)


def test_engine_cancels_pressed_state_before_post_gap_release_evidence() -> None:
    engine = GestureEngine.from_settings(GestureSettings(temple_stabilization_ms=0))
    engine.update_temple(feature(1, 0.00, right=0.20))
    engine.update_temple(feature(2, 0.10, right=0.05))
    engine.update_temple(feature(3, 0.11, right=0.05))

    result = engine.update_temple(feature(4, 1.00, right=0.20))

    assert result.events == ()


def test_engine_ends_hold_once_before_consuming_post_gap_evidence() -> None:
    engine = GestureEngine.from_settings(
        GestureSettings(
            temple_stabilization_ms=0,
            temple_hold_threshold_ms=100,
        )
    )
    engine.update_temple(feature(1, 0.00, right=0.20))
    engine.update_temple(feature(2, 0.10, right=0.05))
    engine.update_temple(feature(3, 0.11, right=0.05))
    started = engine.update_temple(feature(4, 0.21, right=0.05))

    ended = engine.update_temple(feature(5, 1.00, right=0.20))

    assert event_types(started.events) == [GestureEventType.RIGHT_TEMPLE_HOLD_START]
    assert event_types(ended.events) == [GestureEventType.RIGHT_TEMPLE_HOLD_END]


def test_malformed_expired_observation_cannot_desynchronize_active_hold() -> None:
    engine = GestureEngine.from_settings(
        GestureSettings(
            temple_stabilization_ms=0,
            temple_hold_threshold_ms=100,
        )
    )
    engine.update_temple(feature(1, 0.00, right=0.20))
    engine.update_temple(feature(2, 0.10, right=0.05))
    engine.update_temple(feature(3, 0.11, right=0.05))
    engine.update_temple(feature(4, 0.21, right=0.05))
    malformed = feature(
        5,
        0.30,
        right=0.05,
        processed_timestamp=math.nan,
        status=TempleFeatureStatus.EXPIRED,
    )

    assert engine.update_temple(malformed).events == ()
    ended = engine.poll_temple(0.50)

    assert event_types(ended.events) == [GestureEventType.RIGHT_TEMPLE_HOLD_END]


def test_invalid_reset_time_falls_back_to_latest_evidence_for_hold_end() -> None:
    detector = TempleGestureDetector(TempleGestureSettings(hold_threshold=0.2))
    arm(detector)
    detector.update(snapshot(2, 0.10, left=ProximityState.NEAR))
    detector.update(snapshot(3, 0.30, left=ProximityState.NEAR))

    events = detector.reset(math.nan)

    assert event_types(events) == [GestureEventType.LEFT_TEMPLE_HOLD_END]
    assert events[0].timestamp == 0.30
