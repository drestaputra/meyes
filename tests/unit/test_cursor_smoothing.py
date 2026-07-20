"""Adaptive normalized-point smoothing tests."""

from __future__ import annotations

from typing import Any

import pytest

from meyes.calibration.mapper import NormalizedScreenPoint
from meyes.cursor.smoothing import OneEuroFilterSettings, OneEuroPointFilter


def point(x: float, y: float | None = None) -> NormalizedScreenPoint:
    return NormalizedScreenPoint(x, x if y is None else y)


def test_first_point_passes_through_and_reset_discards_history() -> None:
    smoother = OneEuroPointFilter()

    assert smoother.update(point(0.25, 0.75), timestamp=1.0) == point(0.25, 0.75)
    initialized_before_reset = smoother.initialized
    timestamp_before_reset = smoother.last_timestamp
    assert initialized_before_reset
    assert timestamp_before_reset == 1.0

    smoother.reset()

    initialized_after_reset = smoother.initialized
    timestamp_after_reset = smoother.last_timestamp
    assert not initialized_after_reset
    assert timestamp_after_reset is None
    assert smoother.update(point(0.8, 0.2), timestamp=0.0) == point(0.8, 0.2)


def test_small_alternating_jitter_is_reduced() -> None:
    smoother = OneEuroPointFilter(OneEuroFilterSettings(minimum_cutoff=1.0, speed_coefficient=0.0))
    raw = [0.48 if index % 2 == 0 else 0.52 for index in range(60)]
    output = [
        smoother.update(point(value), timestamp=index / 60.0).x for index, value in enumerate(raw)
    ]

    raw_deviation = sum(abs(value - 0.5) for value in raw[20:]) / 40
    output_deviation = sum(abs(value - 0.5) for value in output[20:]) / 40
    assert output_deviation < raw_deviation * 0.2


def test_speed_coefficient_keeps_rapid_intentional_move_more_responsive() -> None:
    fixed = OneEuroPointFilter(OneEuroFilterSettings(minimum_cutoff=0.5, speed_coefficient=0.0))
    adaptive = OneEuroPointFilter(OneEuroFilterSettings(minimum_cutoff=0.5, speed_coefficient=0.2))
    for smoother in (fixed, adaptive):
        smoother.update(point(0.1), timestamp=0.0)

    fixed_move = fixed.update(point(0.9), timestamp=1.0 / 60.0)
    adaptive_move = adaptive.update(point(0.9), timestamp=1.0 / 60.0)

    assert adaptive_move.x > fixed_move.x
    assert abs(0.9 - adaptive_move.x) < abs(0.9 - fixed_move.x)


def test_axes_adapt_independently() -> None:
    smoother = OneEuroPointFilter(OneEuroFilterSettings(minimum_cutoff=0.5, speed_coefficient=0.2))
    smoother.update(point(0.1, 0.4), timestamp=0.0)

    moved = smoother.update(point(0.9, 0.4), timestamp=1.0 / 60.0)

    assert moved.x > 0.1
    assert moved.y == pytest.approx(0.4)


def test_stale_gap_reseeds_without_interpolating_old_history() -> None:
    smoother = OneEuroPointFilter(OneEuroFilterSettings(maximum_gap_seconds=0.25))
    smoother.update(point(0.1), timestamp=1.0)
    smoother.update(point(0.2), timestamp=1.1)

    assert smoother.update(point(0.9), timestamp=1.36) == point(0.9)
    assert smoother.last_timestamp == 1.36


def test_rejected_timestamp_does_not_mutate_filter_state() -> None:
    smoother = OneEuroPointFilter()
    smoother.update(point(0.2), timestamp=1.0)

    with pytest.raises(ValueError, match="increase strictly"):
        smoother.update(point(0.9), timestamp=1.0)

    assert smoother.last_timestamp == 1.0
    later = smoother.update(point(0.2), timestamp=1.1)
    assert later == point(0.2)


def test_numeric_overflow_fails_before_filter_state_mutation() -> None:
    smoother = OneEuroPointFilter()
    smoother.update(point(1e308), timestamp=0.0)

    with pytest.raises(ValueError, match="numerically unstable"):
        smoother.update(point(-1e308), timestamp=1e-300)

    assert smoother.last_timestamp == 0.0


@pytest.mark.parametrize(
    "arguments",
    [
        {"minimum_cutoff": 0.0},
        {"speed_coefficient": -0.1},
        {"derivative_cutoff": float("inf")},
        {"maximum_gap_seconds": float("nan")},
    ],
)
def test_settings_reject_invalid_values(arguments: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="must be"):
        OneEuroFilterSettings(**arguments)


def test_invalid_points_timestamps_and_settings_type_fail_closed() -> None:
    with pytest.raises(TypeError, match="OneEuroFilterSettings"):
        OneEuroPointFilter(object())  # type: ignore[arg-type]
    smoother = OneEuroPointFilter()
    with pytest.raises(TypeError, match="NormalizedScreenPoint"):
        smoother.update(object(), timestamp=0.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="point must be finite"):
        smoother.update(point(float("nan")), timestamp=0.0)
    with pytest.raises(ValueError, match="timestamp"):
        smoother.update(point(0.5), timestamp=float("inf"))
