"""Dormant normalized-to-physical-pixel mapping for one validated primary screen."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from meyes.calibration.mapper import NormalizedScreenPoint

_INT32_MIN = -(2**31)
_INT32_MAX = 2**31 - 1


@dataclass(frozen=True, slots=True)
class PhysicalScreenGeometry:
    """Inclusive Windows physical-pixel bounds, never Qt logical coordinates."""

    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        for name, value in (("left", self.left), ("top", self.top)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"Screen {name} must be an integer")
            if not _INT32_MIN <= value <= _INT32_MAX:
                raise ValueError(f"Screen {name} must fit a signed 32-bit coordinate")
        for name, value in (("width", self.width), ("height", self.height)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"Screen {name} must be an integer")
            if value < 1:
                raise ValueError(f"Screen {name} must be positive")
        if self.right > _INT32_MAX or self.bottom > _INT32_MAX:
            raise ValueError("Screen bounds must fit signed 32-bit coordinates")

    @property
    def right(self) -> int:
        return self.left + self.width - 1

    @property
    def bottom(self) -> int:
        return self.top + self.height - 1


@dataclass(frozen=True, slots=True)
class PhysicalScreenPoint:
    """One integer physical-pixel coordinate."""

    x: int
    y: int


@dataclass(frozen=True, slots=True)
class ScreenMappingResult:
    """Mapped point plus transparent evidence that an axis was clamped."""

    point: PhysicalScreenPoint
    horizontal_clamped: bool
    vertical_clamped: bool

    @property
    def clamped(self) -> bool:
        return self.horizontal_clamped or self.vertical_clamped


@runtime_checkable
class ScreenCoordinateMapper(Protocol):
    """Replaceable mapping boundary with no executor dependency."""

    def map(self, point: NormalizedScreenPoint) -> ScreenMappingResult: ...


class PrimaryScreenMapper:
    """Clamp normalized predictions and map them to inclusive physical-pixel bounds."""

    def __init__(self, geometry: PhysicalScreenGeometry) -> None:
        if not isinstance(geometry, PhysicalScreenGeometry):
            raise TypeError("Expected PhysicalScreenGeometry")
        self._geometry = geometry

    @property
    def geometry(self) -> PhysicalScreenGeometry:
        return self._geometry

    def map(self, point: NormalizedScreenPoint) -> ScreenMappingResult:
        if not isinstance(point, NormalizedScreenPoint):
            raise TypeError("Expected NormalizedScreenPoint")
        if not _finite(point.x) or not _finite(point.y):
            raise ValueError("Normalized screen point must be finite")
        normalized_x = min(1.0, max(0.0, float(point.x)))
        normalized_y = min(1.0, max(0.0, float(point.y)))
        x = self._geometry.left + _nearest_pixel(normalized_x, self._geometry.width)
        y = self._geometry.top + _nearest_pixel(normalized_y, self._geometry.height)
        return ScreenMappingResult(
            PhysicalScreenPoint(x, y),
            horizontal_clamped=normalized_x != point.x,
            vertical_clamped=normalized_y != point.y,
        )


def _nearest_pixel(normalized: float, extent: int) -> int:
    return math.floor(normalized * (extent - 1) + 0.5)


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
