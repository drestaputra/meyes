"""Replaceable polynomial gaze-to-screen calibration mapping."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from meyes.calibration.session import (
    CALIBRATION_TARGETS,
    CalibrationSample,
    CalibrationTarget,
    CalibrationTargetName,
)
from meyes.domain.observations import GazeFeatureVector

_BASIS_SIZE = 6
DEFAULT_MAXIMUM_CONDITION_NUMBER = 1e12


@dataclass(frozen=True, slots=True)
class NormalizedScreenPoint:
    """Unclamped normalized screen prediction from a calibration mapper."""

    x: float
    y: float


@runtime_checkable
class CalibrationMapper(Protocol):
    """Replaceable fitted mapper contract."""

    def predict(self, feature: GazeFeatureVector) -> NormalizedScreenPoint: ...


@dataclass(frozen=True, slots=True)
class PolynomialCalibrationMapper:
    """Immutable quadratic mapper with independently fitted x/y coefficients."""

    horizontal_coefficients: tuple[float, ...]
    vertical_coefficients: tuple[float, ...]

    def __post_init__(self) -> None:
        for coefficients in (self.horizontal_coefficients, self.vertical_coefficients):
            if (
                not isinstance(coefficients, tuple)
                or len(coefficients) != _BASIS_SIZE
                or not all(_finite_number(value) for value in coefficients)
            ):
                raise ValueError("Polynomial coefficients must contain six finite values")

    def predict(self, feature: GazeFeatureVector) -> NormalizedScreenPoint:
        """Predict without clamping so validation can observe boundary error honestly."""
        basis = _feature_basis(feature)
        x = sum(
            value * coefficient
            for value, coefficient in zip(
                basis,
                self.horizontal_coefficients,
                strict=True,
            )
        )
        y = sum(
            value * coefficient
            for value, coefficient in zip(
                basis,
                self.vertical_coefficients,
                strict=True,
            )
        )
        if not _finite_number(x) or not _finite_number(y):
            raise ValueError("Calibration prediction is non-finite")
        return NormalizedScreenPoint(x=float(x), y=float(y))


@dataclass(frozen=True, slots=True)
class CalibrationValidation:
    """Held-out normalized Euclidean error metrics."""

    sample_count: int
    root_mean_square_error: float
    mean_error: float
    maximum_error: float


@dataclass(frozen=True, slots=True)
class CalibrationFitResult:
    """Final all-sample mapper plus deterministic holdout evidence."""

    mapper: PolynomialCalibrationMapper
    validation: CalibrationValidation


def fit_polynomial_mapper(
    samples: Sequence[CalibrationSample],
    *,
    minimum_samples_per_target: int = 1,
    maximum_condition_number: float = DEFAULT_MAXIMUM_CONDITION_NUMBER,
) -> PolynomialCalibrationMapper:
    """Fit a quadratic mapper or fail when target coverage/numerics are unsafe."""
    values = _validated_samples(samples, minimum_samples_per_target=minimum_samples_per_target)
    if not _finite_number(maximum_condition_number) or maximum_condition_number <= 1:
        raise ValueError("Maximum condition number must be finite and greater than one")
    design = np.asarray([_feature_basis(sample.feature) for sample in values], dtype=np.float64)
    targets = np.asarray(
        [(_target(sample.target).x, _target(sample.target).y) for sample in values],
        dtype=np.float64,
    )
    rank = int(np.linalg.matrix_rank(design))
    if rank < _BASIS_SIZE:
        raise ValueError("Calibration feature geometry is rank deficient")
    condition = float(np.linalg.cond(design))
    if not math.isfinite(condition) or condition > maximum_condition_number:
        raise ValueError("Calibration feature geometry is ill-conditioned")
    coefficients, _residuals, fitted_rank, _singular = np.linalg.lstsq(design, targets, rcond=None)
    if int(fitted_rank) < _BASIS_SIZE or not np.isfinite(coefficients).all():
        raise ValueError("Calibration mapper fit failed")
    typed = coefficients.astype(np.float64, copy=False)
    return PolynomialCalibrationMapper(
        horizontal_coefficients=_column_tuple(typed, 0),
        vertical_coefficients=_column_tuple(typed, 1),
    )


def fit_and_validate_polynomial_mapper(
    samples: Sequence[CalibrationSample],
    *,
    holdout_per_target: int = 2,
    maximum_condition_number: float = DEFAULT_MAXIMUM_CONDITION_NUMBER,
) -> CalibrationFitResult:
    """Validate on deterministic per-target holdouts, then fit the final all-sample mapper."""
    if (
        isinstance(holdout_per_target, bool)
        or not isinstance(holdout_per_target, int)
        or holdout_per_target < 1
    ):
        raise ValueError("Holdout samples per target must be a positive integer")
    values = _validated_samples(samples, minimum_samples_per_target=holdout_per_target + 1)
    groups: dict[CalibrationTargetName, list[CalibrationSample]] = defaultdict(list)
    for sample in values:
        groups[sample.target].append(sample)
    training: list[CalibrationSample] = []
    holdout: list[CalibrationSample] = []
    for target in CALIBRATION_TARGETS:
        ordered = sorted(
            groups[target.name],
            key=lambda sample: (sample.source_sequence, sample.capture_timestamp),
        )
        training.extend(ordered[:-holdout_per_target])
        holdout.extend(ordered[-holdout_per_target:])
    validation_mapper = fit_polynomial_mapper(
        training,
        maximum_condition_number=maximum_condition_number,
    )
    validation = evaluate_mapper(validation_mapper, holdout)
    final_mapper = fit_polynomial_mapper(
        values,
        maximum_condition_number=maximum_condition_number,
    )
    return CalibrationFitResult(mapper=final_mapper, validation=validation)


def evaluate_mapper(
    mapper: CalibrationMapper,
    samples: Sequence[CalibrationSample],
) -> CalibrationValidation:
    """Measure normalized Euclidean error without applying an acceptance threshold."""
    if not isinstance(mapper, CalibrationMapper):
        raise TypeError("Expected CalibrationMapper")
    values = tuple(samples)
    if not values:
        raise ValueError("Calibration validation requires samples")
    errors: list[float] = []
    for sample in values:
        _validate_sample(sample)
        prediction = mapper.predict(sample.feature)
        if not isinstance(prediction, NormalizedScreenPoint):
            raise TypeError("CalibrationMapper must return NormalizedScreenPoint")
        if not _finite_number(prediction.x) or not _finite_number(prediction.y):
            raise ValueError("Calibration mapper prediction must be finite")
        target = _target(sample.target)
        error = math.hypot(prediction.x - target.x, prediction.y - target.y)
        if not math.isfinite(error):
            raise ValueError("Calibration validation error is non-finite")
        errors.append(error)
    squared_mean = sum(error * error for error in errors) / len(errors)
    return CalibrationValidation(
        sample_count=len(errors),
        root_mean_square_error=math.sqrt(squared_mean),
        mean_error=sum(errors) / len(errors),
        maximum_error=max(errors),
    )


def _validated_samples(
    samples: Sequence[CalibrationSample],
    *,
    minimum_samples_per_target: int,
) -> tuple[CalibrationSample, ...]:
    if (
        isinstance(minimum_samples_per_target, bool)
        or not isinstance(minimum_samples_per_target, int)
        or minimum_samples_per_target < 1
    ):
        raise ValueError("Minimum samples per target must be a positive integer")
    values = tuple(samples)
    groups: dict[CalibrationTargetName, int] = defaultdict(int)
    for sample in values:
        _validate_sample(sample)
        groups[sample.target] += 1
    missing = [
        target.name.value
        for target in CALIBRATION_TARGETS
        if groups[target.name] < minimum_samples_per_target
    ]
    if missing:
        raise ValueError("Calibration samples do not cover every target sufficiently")
    target_order = {target.name: index for index, target in enumerate(CALIBRATION_TARGETS)}
    return tuple(
        sorted(
            values,
            key=lambda sample: (
                target_order[sample.target],
                sample.source_sequence,
                sample.capture_timestamp,
                sample.feature.horizontal,
                sample.feature.vertical,
            ),
        )
    )


def _validate_sample(sample: object) -> None:
    if not isinstance(sample, CalibrationSample):
        raise TypeError("Expected CalibrationSample")
    if not isinstance(sample.target, CalibrationTargetName):
        raise ValueError("Calibration sample target is invalid")
    if (
        isinstance(sample.source_sequence, bool)
        or not isinstance(sample.source_sequence, int)
        or sample.source_sequence <= 0
        or not _finite_number(sample.capture_timestamp)
    ):
        raise ValueError("Calibration sample metadata is invalid")
    _feature_basis(sample.feature)


def _feature_basis(feature: GazeFeatureVector) -> tuple[float, ...]:
    if not isinstance(feature, GazeFeatureVector):
        raise TypeError("Expected GazeFeatureVector")
    horizontal = feature.horizontal
    vertical = feature.vertical
    if not _finite_number(horizontal) or not _finite_number(vertical):
        raise ValueError("Gaze feature must be finite")
    return (
        1.0,
        float(horizontal),
        float(vertical),
        float(horizontal * horizontal),
        float(horizontal * vertical),
        float(vertical * vertical),
    )


def _target(name: CalibrationTargetName) -> CalibrationTarget:
    return next(target for target in CALIBRATION_TARGETS if target.name is name)


def _column_tuple(matrix: NDArray[np.float64], column: int) -> tuple[float, ...]:
    return tuple(float(value) for value in matrix[:, column])


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
