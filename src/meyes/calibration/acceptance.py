"""Completion acceptance plus optional stricter calibration evidence limits."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from meyes.calibration.mapper import CalibrationFitResult, CalibrationValidation


class CalibrationAcceptanceState(StrEnum):
    """Whether the current acceptance path approves a volatile mapper."""

    REVIEW_REQUIRED = "review_required"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class CalibrationAcceptancePolicy:
    """Caller-supplied limits; MEYES deliberately provides no universal defaults."""

    maximum_root_mean_square_error: float
    maximum_mean_error: float
    maximum_error: float
    minimum_holdout_samples: int

    def __post_init__(self) -> None:
        limits = (
            self.maximum_root_mean_square_error,
            self.maximum_mean_error,
            self.maximum_error,
        )
        if not all(_positive_finite(value) for value in limits):
            raise ValueError("Calibration acceptance error limits must be finite and positive")
        if (
            isinstance(self.minimum_holdout_samples, bool)
            or not isinstance(self.minimum_holdout_samples, int)
            or self.minimum_holdout_samples < 1
        ):
            raise ValueError("Minimum holdout samples must be a positive integer")


@dataclass(frozen=True, slots=True)
class CalibrationAcceptance:
    """Transparent decision and any failed completion or configured limits."""

    state: CalibrationAcceptanceState
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AcceptedCalibration:
    """Proof-carrying volatile fit for consumers that require explicit acceptance."""

    fit_result: CalibrationFitResult
    acceptance: CalibrationAcceptance

    def __post_init__(self) -> None:
        if not isinstance(self.fit_result, CalibrationFitResult):
            raise TypeError("Expected CalibrationFitResult")
        if not isinstance(self.acceptance, CalibrationAcceptance):
            raise TypeError("Expected CalibrationAcceptance")
        if self.acceptance.state is not CalibrationAcceptanceState.ACCEPTED:
            raise ValueError("Calibration must be accepted before creating an accepted token")
        if self.acceptance.reasons:
            raise ValueError("Accepted calibration cannot contain rejection reasons")


def review_required_acceptance() -> CalibrationAcceptance:
    """Keep a fitted mapper unaccepted when no evidence-backed limits are configured."""
    return CalibrationAcceptance(
        CalibrationAcceptanceState.REVIEW_REQUIRED,
        ("No complete calibration acceptance policy is configured.",),
    )


def accept_validated_calibration(validation: CalibrationValidation) -> CalibrationAcceptance:
    """Accept a completed pursuit fit when its validation evidence is structurally valid."""
    _validate_evidence(validation)
    return CalibrationAcceptance(CalibrationAcceptanceState.ACCEPTED)


def evaluate_calibration_acceptance(
    policy: CalibrationAcceptancePolicy,
    validation: CalibrationValidation,
) -> CalibrationAcceptance:
    """Evaluate every configured limit without activating or persisting the mapper."""
    if not isinstance(policy, CalibrationAcceptancePolicy):
        raise TypeError("Expected CalibrationAcceptancePolicy")
    _validate_evidence(validation)
    reasons: list[str] = []
    if validation.root_mean_square_error > policy.maximum_root_mean_square_error:
        reasons.append(
            "RMSE "
            f"{validation.root_mean_square_error:.4f} exceeds "
            f"{policy.maximum_root_mean_square_error:.4f}"
        )
    if validation.mean_error > policy.maximum_mean_error:
        reasons.append(f"mean {validation.mean_error:.4f} exceeds {policy.maximum_mean_error:.4f}")
    if validation.maximum_error > policy.maximum_error:
        reasons.append(f"maximum {validation.maximum_error:.4f} exceeds {policy.maximum_error:.4f}")
    if validation.sample_count < policy.minimum_holdout_samples:
        reasons.append(
            f"holdout n={validation.sample_count} is below {policy.minimum_holdout_samples}"
        )
    return CalibrationAcceptance(
        CalibrationAcceptanceState.REJECTED if reasons else CalibrationAcceptanceState.ACCEPTED,
        tuple(reasons),
    )


def _validate_evidence(validation: object) -> None:
    if not isinstance(validation, CalibrationValidation):
        raise TypeError("Expected CalibrationValidation")
    metrics = (
        validation.root_mean_square_error,
        validation.mean_error,
        validation.maximum_error,
    )
    if not all(_non_negative_finite(value) for value in metrics):
        raise ValueError("Calibration validation metrics must be finite and non-negative")
    if (
        isinstance(validation.sample_count, bool)
        or not isinstance(validation.sample_count, int)
        or validation.sample_count < 1
    ):
        raise ValueError("Calibration validation sample count must be positive")


def _positive_finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _non_negative_finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )
