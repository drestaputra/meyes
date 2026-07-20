"""Robust per-target calibration sample outlier selection."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import median

from meyes.domain.observations import GazeFeatureVector

MINIMUM_OUTLIER_SAMPLES = 5
DEFAULT_MAD_SCALE = 3.5
DEFAULT_MINIMUM_RADIUS = 0.02
_NORMAL_MAD_SCALE = 1.4826


def select_gaze_feature_inliers(
    features: Sequence[GazeFeatureVector],
    *,
    minimum_samples: int = MINIMUM_OUTLIER_SAMPLES,
    mad_scale: float = DEFAULT_MAD_SCALE,
    minimum_radius: float = DEFAULT_MINIMUM_RADIUS,
) -> tuple[int, ...]:
    """Return stable indices inside coordinate-wise median/MAD bounds."""
    if isinstance(minimum_samples, bool) or not isinstance(minimum_samples, int):
        raise TypeError("minimum_samples must be an integer")
    if minimum_samples < 3:
        raise ValueError("minimum_samples must be at least 3")
    if not _finite_number(mad_scale) or mad_scale <= 0:
        raise ValueError("mad_scale must be finite and positive")
    if not _finite_number(minimum_radius) or minimum_radius < 0:
        raise ValueError("minimum_radius must be finite and non-negative")
    values = tuple(features)
    for feature in values:
        if not isinstance(feature, GazeFeatureVector):
            raise TypeError("Expected GazeFeatureVector samples")
        if not _finite_number(feature.horizontal) or not _finite_number(feature.vertical):
            raise ValueError("Gaze feature samples must be finite")
    if len(values) < minimum_samples:
        return tuple(range(len(values)))

    horizontal = tuple(feature.horizontal for feature in values)
    vertical = tuple(feature.vertical for feature in values)
    horizontal_center = float(median(horizontal))
    vertical_center = float(median(vertical))
    horizontal_mad = float(median(abs(value - horizontal_center) for value in horizontal))
    vertical_mad = float(median(abs(value - vertical_center) for value in vertical))
    horizontal_radius = max(
        float(minimum_radius),
        float(mad_scale) * _NORMAL_MAD_SCALE * horizontal_mad,
    )
    vertical_radius = max(
        float(minimum_radius),
        float(mad_scale) * _NORMAL_MAD_SCALE * vertical_mad,
    )
    return tuple(
        index
        for index, feature in enumerate(values)
        if abs(feature.horizontal - horizontal_center) <= horizontal_radius
        and abs(feature.vertical - vertical_center) <= vertical_radius
    )


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
