"""Fake-only accepted-calibration cursor pipeline tests."""

from __future__ import annotations

import pytest

from meyes.calibration.acceptance import (
    AcceptedCalibration,
    CalibrationAcceptance,
    CalibrationAcceptanceState,
)
from meyes.calibration.mapper import (
    CalibrationFitResult,
    CalibrationValidation,
    PolynomialCalibrationMapper,
)
from meyes.cursor.gate import CursorGateState
from meyes.cursor.pipeline import CursorPipeline, CursorPipelineStatus
from meyes.cursor.screen_mapping import (
    PhysicalScreenGeometry,
    PhysicalScreenPoint,
    PrimaryScreenMapper,
)
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import (
    GazeFeatureObservation,
    GazeFeatureStatus,
    GazeFeatureVector,
)


def accepted_calibration() -> AcceptedCalibration:
    mapper = PolynomialCalibrationMapper(
        (0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    )
    fit = CalibrationFitResult(mapper, CalibrationValidation(18, 0.01, 0.01, 0.02))
    acceptance = CalibrationAcceptance(CalibrationAcceptanceState.ACCEPTED)
    return AcceptedCalibration(fit, acceptance)


def observation(sequence: int, timestamp: float, x: float, y: float) -> GazeFeatureObservation:
    vector = GazeFeatureVector(x, y)
    return GazeFeatureObservation(
        sequence,
        timestamp,
        timestamp + 0.001,
        GazeFeatureStatus.READY,
        vector,
        vector,
        vector,
    )


def pipeline() -> CursorPipeline:
    return CursorPipeline(
        accepted_calibration(),
        PrimaryScreenMapper(PhysicalScreenGeometry(0, 0, 1920, 1080)),
    )


def test_review_or_rejected_fit_cannot_create_accepted_token() -> None:
    accepted = accepted_calibration()
    for state in (
        CalibrationAcceptanceState.REVIEW_REQUIRED,
        CalibrationAcceptanceState.REJECTED,
    ):
        with pytest.raises(ValueError, match="must be accepted"):
            AcceptedCalibration(accepted.fit_result, CalibrationAcceptance(state))


def test_pipeline_starts_blocked_and_never_exposes_pixel_candidate() -> None:
    cursor = pipeline()

    result = cursor.update(observation(1, 1.0, 0.5, 0.5))

    assert result.status is CursorPipelineStatus.GATE_BLOCKED
    assert result.gate.state is CursorGateState.SUSPENDED
    assert result.normalized is None
    assert result.screen is None


def test_open_pipeline_composes_prediction_smoothing_and_pixel_mapping() -> None:
    cursor = pipeline()
    cursor.resume_tracking(1.0)
    cursor.poll(1.12)

    result = cursor.update(observation(1, 1.13, 0.5, 0.5))

    assert result.status is CursorPipelineStatus.READY
    assert result.normalized is not None
    assert result.screen is not None
    assert result.screen.point == PhysicalScreenPoint(960, 540)


def test_temple_hold_blocks_output_and_reseeds_after_delayed_resume() -> None:
    cursor = pipeline()
    cursor.resume_tracking(1.0)
    cursor.poll(1.12)
    cursor.update(observation(1, 1.13, 0.1, 0.1))
    cursor.handle_event(GestureEvent(GestureEventType.LEFT_TEMPLE_HOLD_START, 1.14, 1, 550.0))

    blocked = cursor.update(observation(2, 1.15, 0.9, 0.9))
    cursor.handle_event(GestureEvent(GestureEventType.LEFT_TEMPLE_HOLD_END, 1.2, 2, 600.0))
    cursor.poll(1.32)
    resumed = cursor.update(observation(3, 1.33, 0.9, 0.9))

    assert blocked.status is CursorPipelineStatus.GATE_BLOCKED
    assert blocked.screen is None
    assert resumed.status is CursorPipelineStatus.READY
    assert resumed.normalized is not None
    assert resumed.normalized.x == pytest.approx(0.9)


def test_unavailable_feature_resets_and_never_maps() -> None:
    cursor = pipeline()
    cursor.resume_tracking(1.0)
    cursor.poll(1.12)
    unavailable = GazeFeatureObservation(1, 1.13, 1.14, GazeFeatureStatus.FACE_NOT_DETECTED)

    result = cursor.update(unavailable)

    assert result.status is CursorPipelineStatus.FEATURE_UNAVAILABLE
    assert result.screen is None
