"""Robust calibration outlier selection tests."""

from __future__ import annotations

from typing import Any, cast

import pytest

from meyes.calibration.outliers import select_gaze_feature_inliers
from meyes.domain.observations import GazeFeatureVector


def vectors(*pairs: tuple[float, float]) -> tuple[GazeFeatureVector, ...]:
    return tuple(GazeFeatureVector(*pair) for pair in pairs)


def test_too_few_samples_preserve_stable_input_order() -> None:
    samples = vectors((0.5, 0.5), (0.51, 0.49), (0.49, 0.51), (0.5, 0.5))

    assert select_gaze_feature_inliers(samples) == (0, 1, 2, 3)


def test_coordinate_wise_median_mad_rejects_horizontal_and_vertical_extremes() -> None:
    samples = vectors(
        (0.50, 0.50),
        (0.51, 0.49),
        (0.49, 0.51),
        (0.50, 0.50),
        (0.90, 0.50),
        (0.50, 0.90),
    )

    assert select_gaze_feature_inliers(samples) == (0, 1, 2, 3)


def test_minimum_radius_avoids_zero_mad_while_rejecting_clear_outlier() -> None:
    samples = vectors((0.5, 0.5), (0.5, 0.5), (0.5, 0.5), (0.5, 0.5), (0.53, 0.5))

    assert select_gaze_feature_inliers(samples) == (0, 1, 2, 3)
    assert select_gaze_feature_inliers(samples, minimum_radius=0.04) == (0, 1, 2, 3, 4)


def test_runtime_arguments_and_samples_are_validated() -> None:
    sample = (
        vectors(
            (0.5, 0.5),
        )
        * 5
    )

    with pytest.raises(TypeError, match="integer"):
        select_gaze_feature_inliers(sample, minimum_samples=cast(Any, True))
    with pytest.raises(ValueError, match="at least 3"):
        select_gaze_feature_inliers(sample, minimum_samples=2)
    with pytest.raises(ValueError, match="positive"):
        select_gaze_feature_inliers(sample, mad_scale=0)
    with pytest.raises(ValueError, match="non-negative"):
        select_gaze_feature_inliers(sample, minimum_radius=-0.1)
    with pytest.raises(TypeError, match="Expected GazeFeatureVector"):
        select_gaze_feature_inliers(cast(Any, [object()] * 5))
    with pytest.raises(ValueError, match="finite"):
        select_gaze_feature_inliers(vectors(*([(0.5, 0.5)] * 4), (float("nan"), 0.5)))
