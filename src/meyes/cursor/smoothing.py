"""Timestamp-aware adaptive smoothing for normalized calibration predictions."""

from __future__ import annotations

import math
from dataclasses import dataclass

from meyes.calibration.mapper import NormalizedScreenPoint


@dataclass(frozen=True, slots=True)
class OneEuroFilterSettings:
    """One Euro parameters and the stale-gap reset boundary."""

    minimum_cutoff: float = 1.0
    speed_coefficient: float = 0.01
    derivative_cutoff: float = 1.0
    maximum_gap_seconds: float = 0.25

    def __post_init__(self) -> None:
        if not _positive_finite(self.minimum_cutoff):
            raise ValueError("Minimum cutoff must be finite and positive")
        if not _non_negative_finite(self.speed_coefficient):
            raise ValueError("Speed coefficient must be finite and non-negative")
        if not _positive_finite(self.derivative_cutoff):
            raise ValueError("Derivative cutoff must be finite and positive")
        if not _positive_finite(self.maximum_gap_seconds):
            raise ValueError("Maximum gap must be finite and positive")


class OneEuroPointFilter:
    """Smooth independent normalized axes while adapting cutoff to movement speed."""

    def __init__(self, settings: OneEuroFilterSettings | None = None) -> None:
        if settings is not None and not isinstance(settings, OneEuroFilterSettings):
            raise TypeError("Expected OneEuroFilterSettings or None")
        self._settings = settings or OneEuroFilterSettings()
        self._last_timestamp: float | None = None
        self._raw: NormalizedScreenPoint | None = None
        self._filtered: NormalizedScreenPoint | None = None
        self._derivative = NormalizedScreenPoint(0.0, 0.0)

    @property
    def initialized(self) -> bool:
        return self._last_timestamp is not None

    @property
    def last_timestamp(self) -> float | None:
        return self._last_timestamp

    def update(
        self,
        point: NormalizedScreenPoint,
        *,
        timestamp: float,
    ) -> NormalizedScreenPoint:
        """Return one smoothed point or fail without mutating on invalid ordering."""
        _validate_point(point)
        if not _non_negative_finite(timestamp):
            raise ValueError("Smoothing timestamp must be finite and non-negative")
        timestamp_value = float(timestamp)
        if self._last_timestamp is None:
            return self._seed(point, timestamp_value)
        if timestamp_value <= self._last_timestamp:
            raise ValueError("Smoothing timestamps must increase strictly")
        elapsed = timestamp_value - self._last_timestamp
        if elapsed > self._settings.maximum_gap_seconds:
            return self._seed(point, timestamp_value)
        assert self._raw is not None and self._filtered is not None
        derivative_alpha = _alpha(self._settings.derivative_cutoff, elapsed)
        raw_dx = (point.x - self._raw.x) / elapsed
        raw_dy = (point.y - self._raw.y) / elapsed
        if not _finite(raw_dx) or not _finite(raw_dy):
            raise ValueError("Smoothing derivative became numerically unstable")
        derivative = NormalizedScreenPoint(
            _low_pass(raw_dx, self._derivative.x, derivative_alpha),
            _low_pass(raw_dy, self._derivative.y, derivative_alpha),
        )
        x_cutoff = self._settings.minimum_cutoff + self._settings.speed_coefficient * abs(
            derivative.x
        )
        y_cutoff = self._settings.minimum_cutoff + self._settings.speed_coefficient * abs(
            derivative.y
        )
        if not _positive_finite(x_cutoff) or not _positive_finite(y_cutoff):
            raise ValueError("Adaptive smoothing cutoff became numerically unstable")
        filtered = NormalizedScreenPoint(
            _low_pass(point.x, self._filtered.x, _alpha(x_cutoff, elapsed)),
            _low_pass(point.y, self._filtered.y, _alpha(y_cutoff, elapsed)),
        )
        if not _finite(filtered.x) or not _finite(filtered.y):
            raise ValueError("Smoothed point became numerically unstable")
        self._last_timestamp = timestamp_value
        self._raw = point
        self._filtered = filtered
        self._derivative = derivative
        return filtered

    def reset(self) -> None:
        """Discard all history before tracking suspension, mapper replacement, or shutdown."""
        self._last_timestamp = None
        self._raw = None
        self._filtered = None
        self._derivative = NormalizedScreenPoint(0.0, 0.0)

    def _seed(self, point: NormalizedScreenPoint, timestamp: float) -> NormalizedScreenPoint:
        self._last_timestamp = timestamp
        self._raw = point
        self._filtered = point
        self._derivative = NormalizedScreenPoint(0.0, 0.0)
        return point


def _alpha(cutoff: float, elapsed: float) -> float:
    time_constant = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + time_constant / elapsed)


def _low_pass(value: float, previous: float, alpha: float) -> float:
    return (1.0 - alpha) * previous + alpha * value


def _validate_point(point: object) -> None:
    if not isinstance(point, NormalizedScreenPoint):
        raise TypeError("Expected NormalizedScreenPoint")
    if not _finite(point.x) or not _finite(point.y):
        raise ValueError("Normalized screen point must be finite")


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


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
