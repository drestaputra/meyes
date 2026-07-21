"""Deterministic per-side temple proximity state-machine tests."""

from __future__ import annotations

import math

import pytest

from meyes.config.models import GestureSettings
from meyes.domain.observations import (
    HandSide,
    TempleFeatureObservation,
    TempleFeatureStatus,
    TempleProximity,
)
from meyes.gestures.temple_proximity import (
    ProximitySource,
    ProximityState,
    TempleProximityDetector,
    TempleProximitySettings,
)


def feature(
    sequence: int,
    timestamp: float,
    *,
    status: TempleFeatureStatus = TempleFeatureStatus.READY,
    left: float | None = None,
    right: float | None = None,
    processed_timestamp: float | None = None,
    proximities: tuple[TempleProximity, ...] | None = None,
) -> TempleFeatureObservation:
    if proximities is None:
        items = []
        if left is not None:
            items.append(TempleProximity(HandSide.LEFT, left, 0.9))
        if right is not None:
            items.append(TempleProximity(HandSide.RIGHT, right, 0.9))
        proximities = tuple(items)
    return TempleFeatureObservation(
        source_sequence=sequence,
        capture_timestamp=timestamp,
        processed_timestamp=timestamp if processed_timestamp is None else processed_timestamp,
        status=status,
        proximities=proximities,
    )


def test_defaults_convert_from_persisted_millisecond_settings() -> None:
    persisted = GestureSettings()

    settings = TempleProximitySettings.from_settings(persisted)

    assert settings == TempleProximitySettings(
        enter_ratio=0.075,
        exit_ratio=0.095,
        stabilization=0.180,
        tracking_timeout=0.250,
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"enter_ratio": math.nan}, "finite"),
        ({"enter_ratio": 0.1, "exit_ratio": 0.1}, "enter < exit"),
        ({"stabilization": -0.1}, "non-negative"),
        ({"tracking_timeout": 0.0}, "positive"),
    ],
)
def test_detector_settings_reject_invalid_values(
    kwargs: dict[str, float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        TempleProximitySettings(**kwargs)


def test_initial_snapshot_is_unknown_and_unknown_side_fails_closed() -> None:
    detector = TempleProximityDetector()

    assert detector.snapshot.left is ProximityState.UNKNOWN
    assert detector.snapshot.right is ProximityState.UNKNOWN
    assert detector.snapshot.state(HandSide.UNKNOWN) is ProximityState.UNKNOWN


def test_cheek_source_uses_only_cheek_anchor_distances() -> None:
    detector = TempleProximityDetector(
        TempleProximitySettings(stabilization=0),
        source=ProximitySource.CHEEK,
    )
    first = TempleFeatureObservation(
        source_sequence=1,
        capture_timestamp=1.0,
        processed_timestamp=1.0,
        status=TempleFeatureStatus.READY,
        proximities=(TempleProximity(HandSide.RIGHT, 0.01, 0.9),),
        cheek_proximities=(TempleProximity(HandSide.RIGHT, 0.20, 0.9),),
    )
    second = TempleFeatureObservation(
        source_sequence=2,
        capture_timestamp=1.01,
        processed_timestamp=1.01,
        status=TempleFeatureStatus.READY,
        proximities=(TempleProximity(HandSide.RIGHT, 0.20, 0.9),),
        cheek_proximities=(TempleProximity(HandSide.RIGHT, 0.01, 0.9),),
    )
    third = TempleFeatureObservation(
        source_sequence=3,
        capture_timestamp=1.02,
        processed_timestamp=1.02,
        status=TempleFeatureStatus.READY,
        cheek_proximities=(TempleProximity(HandSide.RIGHT, 0.01, 0.9),),
    )

    assert detector.update(first).right is ProximityState.FAR
    assert detector.update(second).right is ProximityState.FAR
    assert detector.update(third).right is ProximityState.NEAR


def test_enter_and_exit_thresholds_are_inclusive_and_stabilized() -> None:
    detector = TempleProximityDetector()

    initial = detector.update(feature(1, 1.0, left=0.2))
    entering = detector.update(feature(2, 1.1, left=0.075))
    still_entering = detector.update(feature(3, 1.279, left=0.075))
    entered = detector.update(feature(4, 1.281, left=0.075))
    releasing = detector.update(feature(5, 1.4, left=0.095))
    still_releasing = detector.update(feature(6, 1.579, left=0.095))
    released = detector.update(feature(7, 1.581, left=0.095))

    assert initial.left is ProximityState.FAR
    assert entering.left is ProximityState.FAR
    assert still_entering.left is ProximityState.FAR
    assert entered.left is ProximityState.NEAR
    assert releasing.left is ProximityState.NEAR
    assert still_releasing.left is ProximityState.NEAR
    assert released.left is ProximityState.FAR


def test_initial_near_requires_a_later_stabilized_sample() -> None:
    detector = TempleProximityDetector(TempleProximitySettings(stabilization=0.0))

    first = detector.update(feature(1, 1.0, left=0.01))
    second = detector.update(feature(2, 1.001, left=0.01))

    assert first.left is ProximityState.UNKNOWN
    assert second.left is ProximityState.NEAR


def test_stabilization_duration_boundary_is_inclusive() -> None:
    detector = TempleProximityDetector(TempleProximitySettings(stabilization=0.25))
    detector.update(feature(1, 1.0, left=0.2))
    detector.update(feature(2, 1.25, left=0.07))

    entered = detector.update(feature(3, 1.5, left=0.07))
    detector.update(feature(4, 1.75))
    released = detector.update(feature(5, 2.0))

    assert entered.left is ProximityState.NEAR
    assert released.left is ProximityState.FAR


def test_entry_jitter_in_dead_band_restarts_candidate() -> None:
    detector = TempleProximityDetector()

    detector.update(feature(1, 1.0, left=0.2))
    detector.update(feature(2, 1.1, left=0.07))
    detector.update(feature(3, 1.2, left=0.08))
    detector.update(feature(4, 1.3, left=0.07))
    too_soon = detector.update(feature(5, 1.479, left=0.07))
    stable = detector.update(feature(6, 1.481, left=0.07))

    assert too_soon.left is ProximityState.FAR
    assert stable.left is ProximityState.NEAR


def test_release_jitter_in_dead_band_restarts_candidate() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 1.0, left=0.07))
    detector.update(feature(2, 1.181, left=0.07))

    detector.update(feature(3, 1.3, left=0.10))
    detector.update(feature(4, 1.4, left=0.08))
    detector.update(feature(5, 1.5, left=0.10))
    too_soon = detector.update(feature(6, 1.679, left=0.10))
    stable = detector.update(feature(7, 1.681, left=0.10))

    assert too_soon.left is ProximityState.NEAR
    assert stable.left is ProximityState.FAR


def test_sides_stabilize_independently_and_snapshots_keep_fixed_order() -> None:
    detector = TempleProximityDetector()

    first = detector.update(feature(1, 1.0, left=0.07, right=0.2))
    second = detector.update(feature(2, 1.181, left=0.07, right=0.07))
    third = detector.update(feature(3, 1.362, left=0.2, right=0.07))

    assert (first.left, first.right) == (ProximityState.UNKNOWN, ProximityState.FAR)
    assert (second.left, second.right) == (ProximityState.NEAR, ProximityState.FAR)
    assert (third.left, third.right) == (ProximityState.NEAR, ProximityState.NEAR)


def test_missing_side_is_far_signal_and_release_is_stabilized() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 1.0, left=0.07))
    detector.update(feature(2, 1.181, left=0.07))

    missing_once = detector.update(feature(3, 1.3, status=TempleFeatureStatus.NO_ELIGIBLE_HANDS))
    missing_stable = detector.update(
        feature(4, 1.481, status=TempleFeatureStatus.NO_ELIGIBLE_HANDS)
    )

    assert missing_once.left is ProximityState.NEAR
    assert missing_stable.left is ProximityState.FAR
    assert missing_stable.right is ProximityState.FAR


def test_invalid_status_retains_stable_state_but_cancels_candidate() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 1.0, left=0.2))
    detector.update(feature(2, 1.1, left=0.07))

    invalid = detector.update(feature(3, 1.2, status=TempleFeatureStatus.PAIR_SKEW))
    restarted = detector.update(feature(4, 1.29, left=0.07))
    too_soon = detector.update(feature(5, 1.469, left=0.07))
    stable = detector.update(feature(6, 1.471, left=0.07))

    assert invalid.left is ProximityState.FAR
    assert restarted.left is ProximityState.FAR
    assert too_soon.left is ProximityState.FAR
    assert stable.left is ProximityState.NEAR


def test_invalid_observation_does_not_block_valid_recompute_at_same_source_time() -> None:
    detector = TempleProximityDetector()

    detector.update(feature(1, 1.0, left=0.2))
    invalid = detector.update(
        feature(
            2,
            1.1,
            status=TempleFeatureStatus.FACE_UNAVAILABLE,
            processed_timestamp=1.15,
        )
    )
    recomputed = detector.update(feature(2, 1.1, left=0.2, processed_timestamp=1.16))

    assert invalid.source_sequence == 1
    assert recomputed.source_sequence == 2
    assert recomputed.timestamp == 1.1


def test_expired_status_resets_both_sides_immediately() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 1.0, left=0.07, right=0.07))
    detector.update(feature(2, 1.181, left=0.07, right=0.07))

    expired = detector.update(feature(2, 1.2, status=TempleFeatureStatus.EXPIRED))

    assert (expired.left, expired.right) == (
        ProximityState.UNKNOWN,
        ProximityState.UNKNOWN,
    )


def test_release_candidate_onset_survives_until_stable_far_transition() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 0.000, right=0.20))
    detector.update(feature(2, 0.100, right=0.05))
    detector.update(feature(3, 0.281, right=0.05))
    detector.update(feature(4, 0.500, right=0.05))
    detector.update(feature(5, 0.700, right=0.05))

    pending = detector.update(feature(6, 0.800, right=0.20))
    completed = detector.update(feature(7, 0.981, right=0.20))

    assert pending.right is ProximityState.NEAR
    assert pending.right_release_started_at == 0.800
    assert completed.right is ProximityState.FAR
    assert completed.right_release_started_at == 0.800


def test_regressing_expiry_processed_time_does_not_reset_active_state() -> None:
    detector = TempleProximityDetector(TempleProximitySettings(stabilization=0))
    detector.update(feature(1, 0.10, right=0.05, processed_timestamp=0.20))
    active = detector.update(feature(2, 0.11, right=0.05, processed_timestamp=0.30))

    regressing = detector.update(
        feature(
            2,
            0.11,
            right=0.05,
            processed_timestamp=0.25,
            status=TempleFeatureStatus.EXPIRED,
        )
    )
    expired = detector.poll(0.56)

    assert active.right is ProximityState.NEAR
    assert regressing.right is ProximityState.NEAR
    assert expired.right is ProximityState.UNKNOWN


def test_malformed_expired_status_does_not_reset_before_a_valid_watchdog_time() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 1.0, left=0.07))
    detector.update(feature(2, 1.181, left=0.07))

    malformed = detector.update(
        feature(
            2,
            1.2,
            status=TempleFeatureStatus.EXPIRED,
            processed_timestamp=math.nan,
        )
    )
    expired = detector.poll(1.5)

    assert malformed.left is ProximityState.NEAR
    assert expired.left is ProximityState.UNKNOWN


def test_poll_timeout_is_strict_and_idempotent() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 10.0, left=0.2))

    boundary = detector.poll(10.250)
    expired = detector.poll(10.251)
    again = detector.poll(11.0)

    assert boundary.left is ProximityState.FAR
    assert expired.left is ProximityState.UNKNOWN
    assert again == expired


def test_invalid_stream_uses_processed_time_for_strict_timeout() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 10.0, left=0.2))

    boundary = detector.update(
        feature(
            2,
            10.1,
            status=TempleFeatureStatus.FACE_UNAVAILABLE,
            processed_timestamp=10.250,
        )
    )
    expired = detector.update(
        feature(
            2,
            10.1,
            status=TempleFeatureStatus.FACE_UNAVAILABLE,
            processed_timestamp=10.251,
        )
    )

    assert boundary.left is ProximityState.FAR
    assert expired.left is ProximityState.UNKNOWN


def test_valid_sample_after_timeout_starts_from_unknown() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 10.0, left=0.2))

    after_gap = detector.update(feature(2, 10.3, left=0.07))

    assert after_gap.left is ProximityState.UNKNOWN


@pytest.mark.parametrize(
    "observation",
    [
        feature(1, 0.9, left=0.2),
        feature(2, 0.9, left=0.2, processed_timestamp=1.1),
        feature(1, 1.1, left=0.2, processed_timestamp=1.2),
    ],
)
def test_duplicate_or_regressing_valid_observations_are_ignored(
    observation: TempleFeatureObservation,
) -> None:
    detector = TempleProximityDetector()
    original = detector.update(feature(1, 1.0, left=0.2, processed_timestamp=1.0))

    result = detector.update(observation)

    assert result == original


def test_capture_time_drives_stabilization_despite_delayed_processing() -> None:
    detector = TempleProximityDetector()

    first = detector.update(feature(1, 10.0, left=0.07, processed_timestamp=10.0))
    delayed = detector.update(feature(2, 10.01, left=0.07, processed_timestamp=10.19))
    stable = detector.update(feature(3, 10.181, left=0.07, processed_timestamp=10.20))

    assert first.left is ProximityState.UNKNOWN
    assert delayed.left is ProximityState.UNKNOWN
    assert stable.left is ProximityState.NEAR


def test_invalid_late_result_expires_from_last_valid_capture_time() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 10.0, left=0.07))
    detector.update(feature(2, 10.181, left=0.07))

    expired = detector.update(
        feature(
            3,
            10.2,
            status=TempleFeatureStatus.FACE_UNAVAILABLE,
            processed_timestamp=10.432,
        )
    )

    assert expired.left is ProximityState.UNKNOWN


def test_stale_valid_sample_is_not_accepted_as_new_evidence() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 10.0, left=0.2))

    stale = detector.update(feature(2, 10.01, left=0.07, processed_timestamp=10.261))

    assert stale.left is ProximityState.UNKNOWN
    assert stale.source_sequence == 1


def test_future_capture_sample_is_not_accepted_as_evidence() -> None:
    detector = TempleProximityDetector()
    original = detector.update(feature(1, 10.0, left=0.2))

    future = detector.update(feature(2, 10.2, left=0.07, processed_timestamp=10.1))

    assert future == original


def test_late_duplicate_can_expire_state_without_becoming_evidence() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 10.0, left=0.2))

    expired = detector.update(feature(1, 10.0, left=0.2, processed_timestamp=10.251))

    assert expired.left is ProximityState.UNKNOWN
    assert expired.source_sequence == 1


def test_no_eligible_hands_with_proximities_is_invalid() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 1.0, left=0.2))
    detector.update(feature(2, 1.1, left=0.07))

    contradictory = detector.update(
        feature(
            3,
            1.2,
            status=TempleFeatureStatus.NO_ELIGIBLE_HANDS,
            left=0.07,
        )
    )
    detector.update(feature(3, 1.2, left=0.07, processed_timestamp=1.21))
    too_soon = detector.update(feature(4, 1.379, left=0.07, processed_timestamp=1.39))
    stable = detector.update(feature(5, 1.381, left=0.07, processed_timestamp=1.40))

    assert contradictory.left is ProximityState.FAR
    assert too_soon.left is ProximityState.FAR
    assert stable.left is ProximityState.NEAR


@pytest.mark.parametrize(
    "proximities",
    [
        (TempleProximity(HandSide.LEFT, math.nan, 0.9),),
        (TempleProximity(HandSide.LEFT, math.inf, 0.9),),
        (TempleProximity(HandSide.LEFT, -0.01, 0.9),),
        (TempleProximity(HandSide.UNKNOWN, 0.01, 0.9),),
        (
            TempleProximity(HandSide.LEFT, 0.01, 0.9),
            TempleProximity(HandSide.LEFT, 0.02, 0.8),
        ),
    ],
)
def test_malformed_ratios_are_invalid_and_cancel_entry_candidate(
    proximities: tuple[TempleProximity, ...],
) -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 1.0, left=0.2))
    detector.update(feature(2, 1.1, left=0.07))

    malformed = detector.update(feature(3, 1.2, proximities=proximities))
    detector.update(feature(3, 1.2, left=0.07, processed_timestamp=1.21))
    too_soon = detector.update(feature(4, 1.379, left=0.07, processed_timestamp=1.39))
    stable = detector.update(feature(5, 1.381, left=0.07, processed_timestamp=1.40))

    assert malformed.left is ProximityState.FAR
    assert too_soon.left is ProximityState.FAR
    assert stable.left is ProximityState.NEAR


def test_reset_clears_state_and_accepts_a_restarted_sequence() -> None:
    detector = TempleProximityDetector()
    detector.update(feature(1, 1.0, left=0.2))

    detector.reset()
    restarted = detector.update(feature(1, 0.5, left=0.2))

    assert restarted.source_sequence == 1
    assert restarted.left is ProximityState.FAR
