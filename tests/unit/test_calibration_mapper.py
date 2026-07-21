"""Replaceable polynomial calibration mapper tests."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, cast

import pytest

from meyes.calibration.mapper import (
    CalibrationMapper,
    NormalizedScreenPoint,
    PolynomialCalibrationMapper,
    evaluate_mapper,
    fit_and_validate_polynomial_mapper,
    fit_polynomial_mapper,
)
from meyes.calibration.session import CALIBRATION_TARGETS, CalibrationSample
from meyes.domain.observations import GazeFeatureVector


def complete_samples(per_target: int = 4) -> tuple[CalibrationSample, ...]:
    samples: list[CalibrationSample] = []
    sequence = 1
    for target in CALIBRATION_TARGETS:
        for _index in range(per_target):
            samples.append(
                CalibrationSample(
                    target=target.name,
                    source_sequence=sequence,
                    capture_timestamp=sequence / 100,
                    feature=GazeFeatureVector(target.x, target.y),
                )
            )
            sequence += 1
    return tuple(samples)


def test_quadratic_mapper_fits_complete_grid_and_predicts_without_clamping() -> None:
    mapper = fit_polynomial_mapper(complete_samples())

    for target in CALIBRATION_TARGETS:
        prediction = mapper.predict(GazeFeatureVector(target.x, target.y))
        assert prediction.x == pytest.approx(target.x, abs=1e-10)
        assert prediction.y == pytest.approx(target.y, abs=1e-10)

    outside = mapper.predict(GazeFeatureVector(1.2, -0.2))
    assert outside.x == pytest.approx(1.2, abs=1e-10)
    assert outside.y == pytest.approx(-0.2, abs=1e-10)
    assert isinstance(mapper, CalibrationMapper)


def test_quadratic_basis_learns_nonlinear_axis_mapping() -> None:
    samples = tuple(
        replace(
            sample,
            feature=GazeFeatureVector(
                math.sqrt(
                    next(target.x for target in CALIBRATION_TARGETS if target.name is sample.target)
                ),
                math.sqrt(
                    next(target.y for target in CALIBRATION_TARGETS if target.name is sample.target)
                ),
            ),
        )
        for sample in complete_samples()
    )
    mapper = fit_polynomial_mapper(samples)

    prediction = mapper.predict(GazeFeatureVector(0.7, 0.8))

    assert prediction.x == pytest.approx(0.49, abs=1e-10)
    assert prediction.y == pytest.approx(0.64, abs=1e-10)


def test_continuous_pursuit_coordinates_are_fitted_instead_of_region_anchors() -> None:
    samples: list[CalibrationSample] = []
    sequence = 1
    for target in CALIBRATION_TARGETS:
        for offset in (-0.03, 0.0, 0.03):
            screen_x = min(max(target.x + offset, 0.05), 0.95)
            screen_y = min(max(target.y - offset, 0.05), 0.95)
            samples.append(
                CalibrationSample(
                    target=target.name,
                    source_sequence=sequence,
                    capture_timestamp=sequence / 30,
                    feature=GazeFeatureVector(screen_x, screen_y),
                    screen_x=screen_x,
                    screen_y=screen_y,
                )
            )
            sequence += 1

    mapper = fit_polynomial_mapper(samples)

    prediction = mapper.predict(GazeFeatureVector(0.37, 0.63))
    assert prediction.x == pytest.approx(0.37, abs=1e-10)
    assert prediction.y == pytest.approx(0.63, abs=1e-10)


def test_robust_fit_limits_one_isolated_camera_outlier() -> None:
    samples = [*complete_samples(per_target=8)]
    samples.append(
        CalibrationSample(
            target=CALIBRATION_TARGETS[0].name,
            source_sequence=len(samples) + 1,
            capture_timestamp=10.0,
            feature=GazeFeatureVector(0.9, 0.9),
        )
    )

    mapper = fit_polynomial_mapper(samples)
    prediction = mapper.predict(GazeFeatureVector(0.5, 0.5))

    assert prediction.x == pytest.approx(0.5, abs=0.01)
    assert prediction.y == pytest.approx(0.5, abs=0.01)


def test_per_target_holdout_is_deterministic_and_final_mapper_uses_all_samples() -> None:
    samples = complete_samples(per_target=4)

    first = fit_and_validate_polynomial_mapper(samples, holdout_per_target=2)
    second = fit_and_validate_polynomial_mapper(tuple(reversed(samples)), holdout_per_target=2)

    assert first == second
    assert first.validation.sample_count == 18
    assert first.validation.root_mean_square_error == pytest.approx(0.0, abs=1e-10)
    assert first.validation.mean_error == pytest.approx(0.0, abs=1e-10)
    assert first.validation.maximum_error == pytest.approx(0.0, abs=1e-10)


def test_evaluate_mapper_accepts_replaceable_protocol_implementation() -> None:
    class IdentityMapper:
        def predict(self, feature: GazeFeatureVector) -> NormalizedScreenPoint:
            return NormalizedScreenPoint(feature.horizontal, feature.vertical)

    validation = evaluate_mapper(IdentityMapper(), complete_samples(per_target=1))

    assert validation.sample_count == 9
    assert validation.root_mean_square_error == pytest.approx(0.0)


def test_missing_target_insufficient_holdout_and_rank_deficiency_fail_closed() -> None:
    samples = complete_samples(per_target=3)

    with pytest.raises(ValueError, match="cover every target"):
        fit_polynomial_mapper(samples[:-3])
    with pytest.raises(ValueError, match="cover every target"):
        fit_and_validate_polynomial_mapper(samples, holdout_per_target=3)
    rank_deficient = tuple(
        replace(sample, feature=GazeFeatureVector(0.5, 0.5)) for sample in samples
    )
    with pytest.raises(ValueError, match="rank deficient"):
        fit_polynomial_mapper(rank_deficient)


def test_condition_limit_and_model_coefficients_are_validated() -> None:
    with pytest.raises(ValueError, match="condition number"):
        fit_polynomial_mapper(complete_samples(), maximum_condition_number=1.0)
    with pytest.raises(ValueError, match="ill-conditioned"):
        fit_polynomial_mapper(complete_samples(), maximum_condition_number=2.0)
    with pytest.raises(ValueError, match="six finite"):
        PolynomialCalibrationMapper((1.0,), (1.0,) * 6)
    with pytest.raises(ValueError, match="six finite"):
        PolynomialCalibrationMapper((float("nan"),) * 6, (1.0,) * 6)
    with pytest.raises(ValueError, match="six finite"):
        PolynomialCalibrationMapper(cast(Any, [1.0] * 6), (1.0,) * 6)


@pytest.mark.parametrize(
    "candidate",
    [
        replace(complete_samples()[0], source_sequence=0),
        replace(complete_samples()[0], capture_timestamp=float("nan")),
        replace(
            complete_samples()[0],
            feature=GazeFeatureVector(float("inf"), 0.5),
        ),
        replace(complete_samples()[0], target=cast(Any, "center")),
    ],
)
def test_invalid_sample_metadata_is_rejected(candidate: CalibrationSample) -> None:
    samples = list(complete_samples())
    samples[0] = candidate

    with pytest.raises(ValueError):
        fit_polynomial_mapper(samples)


def test_runtime_arguments_are_rejected() -> None:
    samples = complete_samples(per_target=3)
    with pytest.raises(ValueError, match="positive integer"):
        fit_and_validate_polynomial_mapper(samples, holdout_per_target=cast(Any, True))
    with pytest.raises(TypeError, match="Expected CalibrationSample"):
        fit_polynomial_mapper(cast(Any, [object()] * 9))
    with pytest.raises(TypeError, match="Expected CalibrationMapper"):
        evaluate_mapper(object(), samples)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="requires samples"):
        evaluate_mapper(fit_polynomial_mapper(samples), ())
    mapper = fit_polynomial_mapper(samples)
    with pytest.raises(TypeError, match="Expected GazeFeatureVector"):
        mapper.predict(object())  # type: ignore[arg-type]


def test_continuous_coordinates_must_be_provided_as_a_pair() -> None:
    with pytest.raises(ValueError, match="provided together"):
        CalibrationSample(
            target=CALIBRATION_TARGETS[0].name,
            source_sequence=1,
            capture_timestamp=1.0,
            feature=GazeFeatureVector(0.1, 0.1),
            screen_x=0.1,
        )


def test_replaceable_mapper_output_is_validated() -> None:
    class WrongTypeMapper:
        def predict(self, feature: GazeFeatureVector) -> NormalizedScreenPoint:
            del feature
            return cast(NormalizedScreenPoint, (0.5, 0.5))

    class NonfiniteMapper:
        def predict(self, feature: GazeFeatureVector) -> NormalizedScreenPoint:
            del feature
            return NormalizedScreenPoint(float("nan"), 0.5)

    samples = complete_samples(per_target=1)
    with pytest.raises(TypeError, match="must return NormalizedScreenPoint"):
        evaluate_mapper(WrongTypeMapper(), samples)
    with pytest.raises(ValueError, match="prediction must be finite"):
        evaluate_mapper(NonfiniteMapper(), samples)
