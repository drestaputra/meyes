"""Live Smooth Pursuit calibration collection tests."""

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
    PursuitAttentionState,
    SmoothPursuitTrajectory,
)
from meyes.domain.observations import (
    GazeFeatureObservation,
    GazeFeatureStatus,
    GazeFeatureVector,
)


def gaze_feature(
    sequence: int,
    *,
    captured: float,
    horizontal: float = 0.5,
    vertical: float = 0.5,
    disagreement: float = 0.04,
) -> GazeFeatureObservation:
    half = disagreement / 2.0
    left = GazeFeatureVector(horizontal - half, vertical - half)
    right = GazeFeatureVector(horizontal + half, vertical + half)
    return GazeFeatureObservation(
        source_sequence=sequence,
        capture_timestamp=captured,
        processed_timestamp=captured + 0.001,
        status=GazeFeatureStatus.READY,
        left_eye=left,
        right_eye=right,
        combined=GazeFeatureVector(horizontal, vertical),
    )


def short_trajectory() -> SmoothPursuitTrajectory:
    return SmoothPursuitTrajectory(
        initial_hold_seconds=0.25,
        leg_duration_seconds=0.5,
        final_hold_seconds=0.25,
    )


def collect_sweep(
    session: CalibrationSession,
    *,
    start: float = 10.0,
    follows_target: bool = True,
    frames_per_second: int = 30,
) -> None:
    session.start()
    session.begin_target(start)
    duration = session.trajectory.duration_seconds
    frame_count = int(duration * frames_per_second)
    for index in range(frame_count):
        elapsed = min((index + 1) / frames_per_second, duration)
        position = session.position_at(start + elapsed)
        horizontal = position.x if follows_target else 0.5
        vertical = position.y if follows_target else 0.5
        result = session.add_feature(
            gaze_feature(
                index + 1,
                captured=start + elapsed,
                horizontal=horizontal,
                vertical=vertical,
            )
        )
        assert result.status is CalibrationCaptureStatus.ACCEPTED


def test_targets_and_serpentine_trajectory_cover_all_screen_regions() -> None:
    assert [target.name for target in CALIBRATION_TARGETS] == list(CalibrationTargetName)
    trajectory = short_trajectory()

    assert trajectory.position_at(-1.0).region is CalibrationTargetName.TOP_LEFT
    assert trajectory.position_at(trajectory.duration_seconds).region is (
        CalibrationTargetName.BOTTOM_RIGHT
    )
    observed = {
        trajectory.position_at(index * trajectory.duration_seconds / 500).region
        for index in range(501)
    }
    assert observed == set(CalibrationTargetName)
    assert trajectory.position_at(trajectory.duration_seconds / 2).progress == pytest.approx(0.5)


def test_successful_sweep_collects_exact_live_positions_and_attention_evidence() -> None:
    session = CalibrationSession(
        samples_per_target=3,
        trajectory=short_trajectory(),
    )
    collect_sweep(session)

    snapshot = session.finish(10.0 + session.trajectory.duration_seconds)

    assert snapshot.state is CalibrationSessionState.COMPLETE
    assert snapshot.completed_targets == 9
    assert snapshot.covered_targets == tuple(CalibrationTargetName)
    assert snapshot.progress == 1.0
    assert snapshot.attention_state is PursuitAttentionState.FOLLOWING
    assert snapshot.horizontal_correlation == pytest.approx(1.0)
    assert snapshot.vertical_correlation == pytest.approx(1.0)
    assert all(
        sample.screen_x is not None and sample.screen_y is not None for sample in session.samples
    )
    assert all(
        sample.target_position == (sample.screen_x, sample.screen_y) for sample in session.samples
    )


def test_sweep_fails_closed_when_eye_features_do_not_follow_target() -> None:
    session = CalibrationSession(
        samples_per_target=3,
        trajectory=short_trajectory(),
    )
    collect_sweep(session, follows_target=False)

    snapshot = session.finish(10.0 + session.trajectory.duration_seconds)

    assert snapshot.state is CalibrationSessionState.TARGET_FAILED
    assert snapshot.attention_state is PursuitAttentionState.ACQUIRING
    assert snapshot.failure_reason is not None
    assert "horizontal eye movement" in snapshot.failure_reason.lower()
    assert "vertical eye movement" in snapshot.failure_reason.lower()


def test_sweep_fails_closed_when_camera_frames_do_not_cover_every_region() -> None:
    trajectory = short_trajectory()
    session = CalibrationSession(samples_per_target=3, trajectory=trajectory)
    session.start()
    session.begin_target(20.0)
    sequence = 1
    for elapsed in (0.1, 0.2, 0.3, 0.4, 0.5, trajectory.duration_seconds):
        position = session.position_at(20.0 + elapsed)
        session.add_feature(
            gaze_feature(
                sequence,
                captured=20.0 + elapsed,
                horizontal=position.x,
                vertical=position.y,
            )
        )
        sequence += 1

    snapshot = session.finish(20.0 + trajectory.duration_seconds)

    assert snapshot.state is CalibrationSessionState.TARGET_FAILED
    assert snapshot.completed_targets < 9
    assert snapshot.failure_reason is not None
    assert "insufficient live samples" in snapshot.failure_reason.lower()


def test_feature_is_ignored_until_live_sweep_is_running() -> None:
    session = CalibrationSession(samples_per_target=3, trajectory=short_trajectory())
    feature = gaze_feature(1, captured=1.0)

    assert session.add_feature(feature).status is CalibrationCaptureStatus.NOT_COLLECTING
    session.start()
    assert session.add_feature(feature).status is CalibrationCaptureStatus.NOT_COLLECTING
    assert session.snapshot.total_samples == 0


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (
            replace(
                gaze_feature(1, captured=10.1),
                status=GazeFeatureStatus.EYES_CLOSED,
                combined=None,
            ),
            CalibrationCaptureStatus.FEATURE_UNAVAILABLE,
        ),
        (
            replace(gaze_feature(1, captured=10.1), left_eye=None),
            CalibrationCaptureStatus.FEATURE_UNAVAILABLE,
        ),
        (
            replace(gaze_feature(1, captured=10.1), source_sequence=0),
            CalibrationCaptureStatus.INVALID_METADATA,
        ),
        (
            replace(gaze_feature(1, captured=10.1), capture_timestamp=float("nan")),
            CalibrationCaptureStatus.INVALID_METADATA,
        ),
        (
            gaze_feature(1, captured=10.1, horizontal=1.6),
            CalibrationCaptureStatus.OUT_OF_RANGE,
        ),
        (
            gaze_feature(1, captured=10.1, disagreement=0.5),
            CalibrationCaptureStatus.EYE_DISAGREEMENT,
        ),
        (
            replace(
                gaze_feature(1, captured=10.1),
                combined=GazeFeatureVector(0.4, 0.5),
            ),
            CalibrationCaptureStatus.INCONSISTENT_COMBINED,
        ),
        (
            replace(
                gaze_feature(1, captured=10.1),
                right_eye=GazeFeatureVector(float("inf"), 0.52),
            ),
            CalibrationCaptureStatus.OUT_OF_RANGE,
        ),
    ],
)
def test_quality_gate_rejects_unusable_live_frames(
    candidate: GazeFeatureObservation,
    expected: CalibrationCaptureStatus,
) -> None:
    session = CalibrationSession(samples_per_target=3, trajectory=short_trajectory())
    session.start()
    session.begin_target(10.0)

    result = session.add_feature(candidate)

    assert result.status is expected
    assert result.sample is None
    assert result.snapshot.total_samples == 0
    assert result.snapshot.rejected_samples == 1


def test_duplicate_sequence_and_nonincreasing_time_are_rejected() -> None:
    session = CalibrationSession(samples_per_target=3, trajectory=short_trajectory())
    session.start()
    session.begin_target(10.0)
    assert session.add_feature(gaze_feature(2, captured=10.1)).status is (
        CalibrationCaptureStatus.ACCEPTED
    )

    duplicate = session.add_feature(gaze_feature(2, captured=10.2))
    old_time = session.add_feature(gaze_feature(3, captured=10.1))

    assert duplicate.status is CalibrationCaptureStatus.OUT_OF_ORDER
    assert old_time.status is CalibrationCaptureStatus.OUT_OF_ORDER
    assert session.snapshot.total_samples == 1
    assert session.snapshot.rejected_samples == 2


def test_frames_before_and_well_after_trajectory_are_rejected() -> None:
    trajectory = short_trajectory()
    session = CalibrationSession(
        samples_per_target=3,
        trajectory=trajectory,
        finish_grace_seconds=0.2,
    )
    session.start()
    session.begin_target(10.0)

    before = session.add_feature(gaze_feature(1, captured=9.9))
    after = session.add_feature(gaze_feature(2, captured=10.0 + trajectory.duration_seconds + 0.3))

    assert before.status is CalibrationCaptureStatus.BEFORE_TRAJECTORY
    assert after.status is CalibrationCaptureStatus.AFTER_TRAJECTORY
    assert session.samples == ()


def test_retry_cancel_reset_and_restart_erase_volatile_samples() -> None:
    session = CalibrationSession(samples_per_target=3, trajectory=short_trajectory())
    session.start()
    session.begin_target(10.0)
    session.add_feature(gaze_feature(1, captured=10.1, horizontal=0.1, vertical=0.1))
    failed = session.finish(10.0 + session.trajectory.duration_seconds)
    assert failed.state is CalibrationSessionState.TARGET_FAILED

    retried = session.begin_target(20.0)
    assert retried.state is CalibrationSessionState.COLLECTING
    assert retried.total_samples == 0
    assert retried.rejected_samples == 0
    assert session.cancel().state is CalibrationSessionState.CANCELLED
    assert session.samples == ()
    assert session.start().state is CalibrationSessionState.AWAITING_TARGET
    assert session.reset().state is CalibrationSessionState.IDLE


def test_invalid_transitions_and_runtime_types_fail_explicitly() -> None:
    session = CalibrationSession(samples_per_target=3, trajectory=short_trajectory())

    with pytest.raises(RuntimeError, match="cannot start"):
        session.begin_target(1.0)
    with pytest.raises(RuntimeError, match="automatically"):
        session.advance()
    with pytest.raises(TypeError, match="Expected GazeFeatureObservation"):
        session.add_feature(object())  # type: ignore[arg-type]
    session.start()
    session.begin_target(10.0)
    with pytest.raises(RuntimeError, match="not complete"):
        session.finish(10.1)


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
        {"minimum_axis_correlation": -0.1},
        {"minimum_axis_correlation": 1.1},
        {"finish_grace_seconds": 6.0},
    ],
)
def test_configuration_is_bounded(arguments: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        CalibrationSession(**arguments)


def test_trajectory_configuration_is_bounded() -> None:
    with pytest.raises(ValueError, match="Leg duration"):
        SmoothPursuitTrajectory(leg_duration_seconds=0.1)
    with pytest.raises(ValueError, match="Initial hold"):
        SmoothPursuitTrajectory(initial_hold_seconds=float("nan"))
