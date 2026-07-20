"""Dormant primary-screen coordinate mapping tests."""

from __future__ import annotations

from typing import Any

import pytest

from meyes.calibration.mapper import NormalizedScreenPoint
from meyes.cursor.screen_mapping import (
    PhysicalScreenGeometry,
    PhysicalScreenPoint,
    PrimaryScreenMapper,
    ScreenCoordinateMapper,
)


def test_primary_screen_corners_center_and_inclusive_endpoints() -> None:
    mapper = PrimaryScreenMapper(PhysicalScreenGeometry(0, 0, 1920, 1080))

    assert isinstance(mapper, ScreenCoordinateMapper)
    assert mapper.map(NormalizedScreenPoint(0.0, 0.0)).point == PhysicalScreenPoint(0, 0)
    assert mapper.map(NormalizedScreenPoint(0.5, 0.5)).point == PhysicalScreenPoint(960, 540)
    assert mapper.map(NormalizedScreenPoint(1.0, 1.0)).point == PhysicalScreenPoint(1919, 1079)


def test_mapping_honors_physical_origin_and_reports_each_clamped_axis() -> None:
    mapper = PrimaryScreenMapper(PhysicalScreenGeometry(-1920, 100, 1920, 1080))

    result = mapper.map(NormalizedScreenPoint(-0.25, 1.5))

    assert result.point == PhysicalScreenPoint(-1920, 1179)
    assert result.horizontal_clamped
    assert result.vertical_clamped
    assert result.clamped


def test_in_range_mapping_is_not_reported_as_clamped() -> None:
    mapper = PrimaryScreenMapper(PhysicalScreenGeometry(10, 20, 101, 201))

    result = mapper.map(NormalizedScreenPoint(0.25, 0.75))

    assert result.point == PhysicalScreenPoint(35, 170)
    assert not result.horizontal_clamped
    assert not result.vertical_clamped
    assert not result.clamped


def test_single_pixel_geometry_maps_every_prediction_to_only_pixel() -> None:
    mapper = PrimaryScreenMapper(PhysicalScreenGeometry(7, 9, 1, 1))

    assert mapper.map(NormalizedScreenPoint(0.0, 1.0)).point == PhysicalScreenPoint(7, 9)


@pytest.mark.parametrize(
    "arguments",
    [
        {"left": True},
        {"top": 1.5},
        {"width": 0},
        {"height": -1},
        {"left": 2**31},
        {"left": 2**31 - 1, "width": 2},
    ],
)
def test_invalid_physical_geometry_fails_closed(arguments: dict[str, Any]) -> None:
    values: dict[str, Any] = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    values.update(arguments)

    with pytest.raises((TypeError, ValueError), match="Screen"):
        PhysicalScreenGeometry(**values)


def test_mapper_rejects_wrong_or_non_finite_predictions() -> None:
    mapper = PrimaryScreenMapper(PhysicalScreenGeometry(0, 0, 1920, 1080))

    with pytest.raises(TypeError, match="NormalizedScreenPoint"):
        mapper.map(object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must be finite"):
        mapper.map(NormalizedScreenPoint(float("nan"), 0.5))
    with pytest.raises(ValueError, match="must be finite"):
        mapper.map(NormalizedScreenPoint(0.5, float("inf")))
    with pytest.raises(TypeError, match="PhysicalScreenGeometry"):
        PrimaryScreenMapper(object())  # type: ignore[arg-type]
