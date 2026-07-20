"""Dormant fail-closed cursor movement gate for tracking and temple interactions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from meyes.domain.events import GestureEvent, GestureEventType


class CursorGateState(StrEnum):
    """Why future cursor movement is allowed or blocked."""

    SUSPENDED = "suspended"
    OPEN = "open"
    TEMPLE_FROZEN = "temple_frozen"
    RESUME_DELAY = "resume_delay"


class TempleSide(StrEnum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class CursorGateSettings:
    freeze_during_temple_gesture: bool = True
    resume_delay_seconds: float = 0.12

    def __post_init__(self) -> None:
        if not isinstance(self.freeze_during_temple_gesture, bool):
            raise TypeError("Freeze-during-temple setting must be a bool")
        if not _non_negative_finite(self.resume_delay_seconds):
            raise ValueError("Resume delay must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class CursorGateSnapshot:
    state: CursorGateState
    active_holds: tuple[TempleSide, ...]
    resume_at: float | None
    movement_allowed: bool


class CursorMovementGate:
    """Serialize semantic events into a conservative future-movement permission."""

    def __init__(self, settings: CursorGateSettings | None = None) -> None:
        if settings is not None and not isinstance(settings, CursorGateSettings):
            raise TypeError("Expected CursorGateSettings or None")
        self._settings = settings or CursorGateSettings()
        self._tracking_available = False
        self._active_holds: set[TempleSide] = set()
        self._resume_at: float | None = None
        self._clock: float | None = None
        self._last_sequence = 0
        self._last_event_key: tuple[GestureEventType, float, int] | None = None

    @property
    def snapshot(self) -> CursorGateSnapshot:
        if not self._tracking_available:
            state = CursorGateState.SUSPENDED
        elif self._settings.freeze_during_temple_gesture and self._active_holds:
            state = CursorGateState.TEMPLE_FROZEN
        elif self._resume_at is not None:
            state = CursorGateState.RESUME_DELAY
        else:
            state = CursorGateState.OPEN
        return CursorGateSnapshot(
            state,
            tuple(sorted(self._active_holds, key=lambda side: side.value)),
            self._resume_at,
            state is CursorGateState.OPEN,
        )

    def handle_event(self, event: GestureEvent) -> CursorGateSnapshot:
        _validate_event(event)
        self._observe_order(event.timestamp, event.source_sequence)
        key = (event.type, event.timestamp, event.source_sequence)
        if key == self._last_event_key:
            return self.snapshot
        self._last_event_key = key
        side, phase = _temple_event(event.type)
        if side is None or phase is None or not self._tracking_available:
            return self.snapshot
        if phase == "start":
            self._active_holds.add(side)
            self._resume_at = None
        elif phase == "end":
            self._active_holds.discard(side)
            if not self._active_holds:
                self._schedule_resume(event.timestamp)
        elif not self._active_holds:
            self._schedule_resume(event.timestamp)
        return self.snapshot

    def poll(self, timestamp: float) -> CursorGateSnapshot:
        value = self._observe_clock(timestamp)
        if (
            self._tracking_available
            and not self._active_holds
            and self._resume_at is not None
            and value >= self._resume_at
        ):
            self._resume_at = None
        return self.snapshot

    def suspend(self, timestamp: float) -> CursorGateSnapshot:
        self._observe_clock(timestamp)
        self._tracking_available = False
        self._active_holds.clear()
        self._resume_at = None
        return self.snapshot

    def resume_tracking(self, timestamp: float) -> CursorGateSnapshot:
        value = self._observe_clock(timestamp)
        self._tracking_available = True
        self._active_holds.clear()
        self._schedule_resume(value)
        return self.snapshot

    def reset(self) -> CursorGateSnapshot:
        self._tracking_available = False
        self._active_holds.clear()
        self._resume_at = None
        self._clock = None
        self._last_sequence = 0
        self._last_event_key = None
        return self.snapshot

    def _schedule_resume(self, timestamp: float) -> None:
        if self._settings.freeze_during_temple_gesture:
            self._resume_at = timestamp + self._settings.resume_delay_seconds
        else:
            self._resume_at = None

    def _observe_order(self, timestamp: float, sequence: int) -> None:
        if not _non_negative_finite(timestamp):
            raise ValueError("Cursor gate timestamp must be finite and non-negative")
        value = float(timestamp)
        if self._clock is not None and value < self._clock:
            raise ValueError("Cursor gate timestamps must not move backward")
        if sequence < self._last_sequence:
            raise ValueError("Gesture source sequences must not move backward")
        self._clock = value
        self._last_sequence = sequence

    def _observe_clock(self, timestamp: float) -> float:
        if not _non_negative_finite(timestamp):
            raise ValueError("Cursor gate timestamp must be finite and non-negative")
        value = float(timestamp)
        if self._clock is not None and value < self._clock:
            raise ValueError("Cursor gate timestamps must not move backward")
        self._clock = value
        return value


def _temple_event(event_type: GestureEventType) -> tuple[TempleSide | None, str | None]:
    mapping = {
        GestureEventType.LEFT_TEMPLE_HOLD_START: (TempleSide.LEFT, "start"),
        GestureEventType.RIGHT_TEMPLE_HOLD_START: (TempleSide.RIGHT, "start"),
        GestureEventType.LEFT_TEMPLE_HOLD_END: (TempleSide.LEFT, "end"),
        GestureEventType.RIGHT_TEMPLE_HOLD_END: (TempleSide.RIGHT, "end"),
        GestureEventType.LEFT_TEMPLE_TAP: (TempleSide.LEFT, "tap"),
        GestureEventType.RIGHT_TEMPLE_TAP: (TempleSide.RIGHT, "tap"),
    }
    return mapping.get(event_type, (None, None))


def _validate_event(event: object) -> None:
    if not isinstance(event, GestureEvent):
        raise TypeError("Expected GestureEvent")
    if not isinstance(event.type, GestureEventType):
        raise ValueError("Gesture event type is invalid")
    if not _non_negative_finite(event.timestamp) or not _non_negative_finite(event.duration_ms):
        raise ValueError("Gesture event timing must be finite and non-negative")
    if (
        isinstance(event.source_sequence, bool)
        or not isinstance(event.source_sequence, int)
        or event.source_sequence < 1
    ):
        raise ValueError("Gesture source sequence must be a positive integer")


def _non_negative_finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )
