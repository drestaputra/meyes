"""Dormant gaze-cursor domain components; no operating-system output is connected."""

from meyes.cursor.gate import (
    CursorGateSettings,
    CursorGateSnapshot,
    CursorGateState,
    CursorMovementGate,
)
from meyes.cursor.pipeline import CursorPipeline, CursorPipelineResult, CursorPipelineStatus
from meyes.cursor.screen_mapping import (
    PhysicalScreenGeometry,
    PhysicalScreenGeometryProvider,
    PhysicalScreenPoint,
    PrimaryScreenMapper,
    ScreenCoordinateMapper,
    ScreenMappingResult,
)
from meyes.cursor.smoothing import OneEuroFilterSettings, OneEuroPointFilter
from meyes.cursor.windows_geometry import (
    CtypesWindowsScreenGeometryApi,
    WindowsPrimaryScreenGeometryProvider,
    WindowsScreenGeometryApi,
    WindowsScreenGeometryError,
)

__all__ = [
    "CtypesWindowsScreenGeometryApi",
    "CursorGateSettings",
    "CursorGateSnapshot",
    "CursorGateState",
    "CursorMovementGate",
    "CursorPipeline",
    "CursorPipelineResult",
    "CursorPipelineStatus",
    "OneEuroFilterSettings",
    "OneEuroPointFilter",
    "PhysicalScreenGeometry",
    "PhysicalScreenGeometryProvider",
    "PhysicalScreenPoint",
    "PrimaryScreenMapper",
    "ScreenCoordinateMapper",
    "ScreenMappingResult",
    "WindowsPrimaryScreenGeometryProvider",
    "WindowsScreenGeometryApi",
    "WindowsScreenGeometryError",
]
