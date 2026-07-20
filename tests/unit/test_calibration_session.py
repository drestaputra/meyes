"""Bounded nine-point calibration collection tests."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest

from meyes.calibration.session import (
    CALIBRATION_TARGETS,
    CalibrationCaptureStatus,
    CalibrationSession,
    CalibrationSessionState,
    CalibrationTargetName,
)
from meyes.domain.observations import (
    GazeFeatureObservation,
    GazeFeatureStatus,
    GazeFeatureVector,
)


def gaze_feature(
    sequence: int,
    *,
    captured: float | None = None,
    horizontal: float = 0.5,
    vertical: float = 0.5,
    disagreement: float = 0.1,
) -> GazeFeatureObservation:
    half = disagreement / 2.0
    left = GazeFeatureVector(horizontal - half, vertical - half)
    right = GazeFeatureVector(horizontal + half, vertical + half)
    return GazeFeatureObservation(
        source_sequence=sequence,
        capture_timestamp=captured if captured is not None else sequence / 100.0,
        processed_timestamp=(captured if captured is not None else sequence / 100.0) + 0.001,
        status=GazeFeatureStatus.READY,
        left_eye=left,
        right_eye=right,
        combined=GazeFeatureVector(horizontal, vertical),
    )


def test_targets_have_stable_row_major_order_and_bounded_coordinates() -> None:
    assert [target.name for target in CALIBRATION_TARGETS] == list(CalibrationTargetName)
    assert [target.label for target in CALIBRATION_TARGETS] == [
        "Top left",
        "Top center",
        "Top right",
        "Middle left",
        "Center",
        "Middle right",
        "Bottom left",
        "Bottom center",
        "Bottom right",
    ]
    assert {(target.x, target.y) for target in CALIBRATION_TARGETS} == {
        (x, y) for y in (0.1, 0.5, 0.9) for x in (0.1, 0.5, 0.9)
    }


def test_complete_session_collects_exact_quota_for_all_nine_targets() -> None:
    session = CalibrationSession(samples_per_target=3, max_attempts_per_target=6)
    sequence = 1

    assert session.start().state is CalibrationSessionState.AWAITING_TARGET
    for target_index, target in enumerate(CALIBRATION_TARGETS):
        started = session.begin_target()
        assert started.target == target
        assert started.target_index == target_index
        for sample_index in range(3):
            result = session.add_feature(gaze_feature(sequence))
            sequence += 1
            expected = (
                CalibrationCaptureStatus.TARGET_COMPLETE
                if sample_index == 2
                else CalibrationCaptureStatus.ACCEPTED
            )
            assert result.status is expected
        advanced = session.advance()
        expected_state = (
            CalibrationSessionState.COMPLETE
            if target_index == 8
            else CalibrationSessionState.AWAITING_TARGET
        )
        assert advanced.state is expected_state

    assert session.snapshot.completed_targets == 9
    assert session.snapshot.total_samples == 27
    assert session.snapshot.target is None
    assert len(session.samples) == 27


def test_feature_is_ignored_until_current_target_is_armed() -> None:
    session = CalibrationSession(samples_per_target=3)
    feature = gaze_feature(1)

    assert session.add_feature(feature).status is CalibrationCaptureStatus.NOT_COLLECTING
    session.start()
    assert session.add_feature(feature).status is CalibrationCaptureStatus.NOT_COLLECTING
    assert session.snapshot.total_samples == 0
    assert session.snapshot.attempts_for_target == 0


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (
            replace(gaze_feature(1), status=GazeFeatureStatus.EYES_CLOSED, combined=None),
            CalibrationCaptureStatus.FEATURE_UNAVAILABLE,
        ),
        (
            replace(gaze_feature(1), left_eye=None),
            CalibrationCaptureStatus.FEATURE_UNAVAILABLE,
        ),
        (
            replace(gaze_feature(1), source_sequence=0),
            CalibrationCaptureStatus.INVALID_METADATA,
        ),
        (
            replace(gaze_feature(1), capture_timestamp=float("nan")),
            CalibrationCaptureStatus.INVALID_METADATA,
        ),
        (
            gaze_feature(1, horizontal=1.6),
            CalibrationCaptureStatus.OUT_OF_RANGE,
        ),
        (
            gaze_feature(1, disagreement=0.5),
            CalibrationCaptureStatus.EYE_DISAGREEMENT,
        ),
        (
            replace(gaze_feature(1), combined=GazeFeatureVector(0.4, 0.5)),
            CalibrationCaptureStatus.INCONSISTENT_COMBINED,
        ),
        (
            replace(
                gaze_feature(1),
                right_eye=GazeFeatureVector(float("inf"), 0.55),
            ),
            CalibrationCaptureStatus.OUT_OF_RANGE,
        ),
    ],
)
def test_quality_gate_rejects_unusable_samples(
    candidate: GazeFeatureObservation,
    expected: CalibrationCaptureStatus,
) -> None:
    session = CalibrationSession(samples_per_target=3, max_attempts_per_target=9)
    session.start()
    session.begin_target()

    result = session.add_feature(candidate)

    assert result.status is expected
    assert result.sample is None
    assert result.snapshot.total_samples == 0
    assert result.snapshot.attempts_for_target == 1


def test_duplicate_sequence_and_nonincreasing_time_are_rejected() -> None:
    session = CalibrationSession(samples_per_target=3, max_attempts_per_target=9)
    session.start()
    session.begin_target()

    assert session.add_feature(gaze_feature(2, captured=1.0)).status is (
        CalibrationCaptureStatus.ACCEPTED
    )
    duplicate = session.add_feature(gaze_feature(2, captured=1.1))
    old_time = session.add_feature(gaze_feature(3, captured=1.0))

    assert duplicate.status is CalibrationCaptureStatus.OUT_OF_ORDER
    assert old_time.status is CalibrationCaptureStatus.OUT_OF_ORDER
    assert session.snapshot.total_samples == 1


def test_attempt_limit_fails_target_and_retry_discards_partial_target_samples() -> None:
    session = CalibrationSession(samples_per_target=3, max_attempts_per_target=3)
    session.start()
    session.begin_target()

    assert session.add_feature(gaze_feature(1)).status is CalibrationCaptureStatus.ACCEPTED
    unavailable = replace(
        gaze_feature(2),
        status=GazeFeatureStatus.EYES_CLOSED,
        combined=None,
    )
    assert session.add_feature(unavailable).status is CalibrationCaptureStatus.FEATURE_UNAVAILABLE
    failed = session.add_feature(replace(unavailable, source_sequence=3, capture_timestamp=0.03))

    assert failed.status is CalibrationCaptureStatus.ATTEMPT_LIMIT
    assert failed.snapshot.state is CalibrationSessionState.TARGET_FAILED
    assert failed.snapshot.total_samples == 1

    retried = session.begin_target()

    assert retried.state is CalibrationSessionState.COLLECTING
    assert retried.total_samples == 0
    assert retried.attempts_for_target == 0


def test_cancel_reset_and_restart_erase_volatile_samples() -> None:
    session = CalibrationSession(samples_per_target=3)
    session.start()
    session.begin_target()
    session.add_feature(gaze_feature(1))

    assert session.cancel().state is CalibrationSessionState.CANCELLED
    assert session.samples == ()
    assert session.start().state is CalibrationSessionState.AWAITING_TARGET
    assert session.reset().state is CalibrationSessionState.IDLE
    assert session.snapshot.total_samples == 0


def test_invalid_transitions_and_runtime_type_fail_explicitly() -> None:
    session = CalibrationSession(samples_per_target=3)

    with pytest.raises(RuntimeError, match="cannot start"):
        session.begin_target()
    with pytest.raises(RuntimeError, match="can advance"):
        session.advance()
    with pytest.raises(TypeError, match="Expected GazeFeatureObservation"):
        session.add_feature(object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "arguments",
    [
        {"samples_per_target": 2},
        {"samples_per_target": cast(Any, True)},
        {"max_attempts_per_target": 2},
        {"max_attempts_per_target": 601},
        {"minimum_feature": float("nan")},
        {"minimum_feature": 1.0, "maximum_feature": 1.0},
        {"maximum_eye_disagreement": -0.1},
    ],
)
def test_configuration_is_bounded(arguments: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        CalibrationSession(**arguments)
