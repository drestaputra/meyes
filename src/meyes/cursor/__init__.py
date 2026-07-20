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
    PhysicalScreenPoint,
    PrimaryScreenMapper,
    ScreenCoordinateMapper,
    ScreenMappingResult,
)
from meyes.cursor.smoothing import OneEuroFilterSettings, OneEuroPointFilter

__all__ = [
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
    "PhysicalScreenPoint",
    "PrimaryScreenMapper",
    "ScreenCoordinateMapper",
    "ScreenMappingResult",
]
