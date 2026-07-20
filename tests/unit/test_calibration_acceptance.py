"""Calibration validation acceptance-policy tests."""

from __future__ import annotations

from typing import Any

import pytest

from meyes.calibration.acceptance import (
    CalibrationAcceptancePolicy,
    CalibrationAcceptanceState,
    evaluate_calibration_acceptance,
    review_required_acceptance,
)
from meyes.calibration.mapper import CalibrationValidation


def evidence(
    *,
    sample_count: int = 18,
    rmse: float = 0.04,
    mean: float = 0.03,
    maximum: float = 0.08,
) -> CalibrationValidation:
    return CalibrationValidation(sample_count, rmse, mean, maximum)


def policy() -> CalibrationAcceptancePolicy:
    return CalibrationAcceptancePolicy(
        maximum_root_mean_square_error=0.05,
        maximum_mean_error=0.04,
        maximum_error=0.10,
        minimum_holdout_samples=18,
    )


def test_no_policy_requires_review_instead_of_implicitly_accepting() -> None:
    outcome = review_required_acceptance()

    assert outcome.state is CalibrationAcceptanceState.REVIEW_REQUIRED
    assert outcome.reasons == ("No complete calibration acceptance policy is configured.",)


def test_every_configured_limit_must_pass_for_acceptance() -> None:
    outcome = evaluate_calibration_acceptance(policy(), evidence())

    assert outcome.state is CalibrationAcceptanceState.ACCEPTED
    assert outcome.reasons == ()


def test_all_failed_limits_are_reported_transparently() -> None:
    outcome = evaluate_calibration_acceptance(
        policy(),
        evidence(sample_count=17, rmse=0.06, mean=0.05, maximum=0.11),
    )

    assert outcome.state is CalibrationAcceptanceState.REJECTED
    assert len(outcome.reasons) == 4
    assert outcome.reasons[0] == "RMSE 0.0600 exceeds 0.0500"
    assert outcome.reasons[-1] == "holdout n=17 is below 18"


@pytest.mark.parametrize(
    "arguments",
    [
        {"maximum_root_mean_square_error": 0.0},
        {"maximum_mean_error": float("inf")},
        {"maximum_error": float("nan")},
        {"minimum_holdout_samples": 0},
        {"minimum_holdout_samples": True},
    ],
)
def test_policy_limits_are_positive_and_finite(arguments: dict[str, Any]) -> None:
    values: dict[str, Any] = {
        "maximum_root_mean_square_error": 0.05,
        "maximum_mean_error": 0.04,
        "maximum_error": 0.10,
        "minimum_holdout_samples": 18,
    }
    values.update(arguments)

    with pytest.raises(ValueError, match="must be"):
        CalibrationAcceptancePolicy(**values)


@pytest.mark.parametrize(
    "candidate",
    [
        CalibrationValidation(0, 0.01, 0.01, 0.01),
        CalibrationValidation(1, float("nan"), 0.01, 0.01),
        CalibrationValidation(1, 0.01, -0.01, 0.01),
    ],
)
def test_invalid_validation_evidence_fails_closed(candidate: CalibrationValidation) -> None:
    with pytest.raises(ValueError, match="Calibration validation"):
        evaluate_calibration_acceptance(policy(), candidate)


def test_acceptance_rejects_wrong_runtime_types() -> None:
    with pytest.raises(TypeError, match="CalibrationAcceptancePolicy"):
        evaluate_calibration_acceptance(object(), evidence())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="CalibrationValidation"):
        evaluate_calibration_acceptance(policy(), object())  # type: ignore[arg-type]
