"""Semantic gesture events emitted before binding or OS input."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GestureEventType(StrEnum):
    """Gesture vocabulary supported by the MEYES domain."""

    LEFT_WINK = "LEFT_WINK"
    RIGHT_WINK = "RIGHT_WINK"
    LEFT_CHEEK_TOUCH = "LEFT_CHEEK_TOUCH"
    RIGHT_CHEEK_TOUCH = "RIGHT_CHEEK_TOUCH"
    LEFT_TEMPLE_TAP = "LEFT_TEMPLE_TAP"
    RIGHT_TEMPLE_TAP = "RIGHT_TEMPLE_TAP"
    LEFT_TEMPLE_HOLD_START = "LEFT_TEMPLE_HOLD_START"
    RIGHT_TEMPLE_HOLD_START = "RIGHT_TEMPLE_HOLD_START"
    LEFT_TEMPLE_HOLD_END = "LEFT_TEMPLE_HOLD_END"
    RIGHT_TEMPLE_HOLD_END = "RIGHT_TEMPLE_HOLD_END"


@dataclass(frozen=True, slots=True)
class GestureEvent:
    """One timestamped semantic event with no action side effects."""

    type: GestureEventType
    timestamp: float
    source_sequence: int
    duration_ms: float
