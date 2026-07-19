"""Framework-independent tap and hold semantics for stable temple states."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeGuard

from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import HandSide
from meyes.gestures.temple_proximity import ProximityState, TempleProximitySnapshot


class TempleInteractionState(StrEnum):
    """Inspectable state for one independently armed temple interaction."""

    WAITING_FOR_FAR = "waiting_for_far"
    IDLE = "idle"
    PRESSED = "pressed"
    HOLDING = "holding"
    COOLDOWN = "cooldown"


@dataclass(frozen=True, slots=True)
class TempleGestureSettings:
    """Tap/hold timing expressed in seconds."""

    hold_threshold: float = 0.550
    cooldown: float = 0.250

    def __post_init__(self) -> None:
        if not math.isfinite(self.hold_threshold) or self.hold_threshold <= 0:
            raise ValueError("Temple hold threshold must be finite and positive")
        if not math.isfinite(self.cooldown) or self.cooldown < 0:
            raise ValueError("Temple cooldown must be finite and non-negative")

    @classmethod
    def from_settings(cls, settings: GestureSettings) -> TempleGestureSettings:
        """Convert persisted millisecond settings into detector units."""
        return cls(
            hold_threshold=settings.temple_hold_threshold_ms / 1000.0,
            cooldown=settings.temple_cooldown_ms / 1000.0,
        )


@dataclass(frozen=True, slots=True)
class TempleGestureDebugState:
    """Immutable state view used by deterministic diagnostics and tests."""

    left: TempleInteractionState
    right: TempleInteractionState


@dataclass(slots=True)
class _SideInteraction:
    state: TempleInteractionState = TempleInteractionState.WAITING_FOR_FAR
    pressed_at: float | None = None
    cooldown_until: float = 0.0

    def observe(
        self,
        *,
        side: HandSide,
        proximity: ProximityState,
        timestamp: float,
        source_sequence: int,
        settings: TempleGestureSettings,
        release_started_at: float | None,
    ) -> tuple[GestureEvent, ...]:
        if proximity is ProximityState.UNKNOWN:
            return self._lose_tracking(side, timestamp, source_sequence, settings)
        if proximity is ProximityState.FAR:
            return self._release_or_arm(
                side,
                timestamp,
                source_sequence,
                settings,
                release_started_at,
            )
        if release_started_at is not None:
            return ()
        return self._press_or_hold(side, timestamp, source_sequence, settings)

    def force_reset(
        self,
        *,
        side: HandSide,
        timestamp: float,
        source_sequence: int,
    ) -> tuple[GestureEvent, ...]:
        events: tuple[GestureEvent, ...] = ()
        if self.state is TempleInteractionState.HOLDING and self.pressed_at is not None:
            events = (
                _event(
                    side,
                    hold_end=True,
                    timestamp=timestamp,
                    source_sequence=source_sequence,
                    duration=timestamp - self.pressed_at,
                ),
            )
        self._wait_for_far()
        return events

    def _press_or_hold(
        self,
        side: HandSide,
        timestamp: float,
        source_sequence: int,
        settings: TempleGestureSettings,
    ) -> tuple[GestureEvent, ...]:
        if self.state is TempleInteractionState.IDLE:
            self.state = TempleInteractionState.PRESSED
            self.pressed_at = timestamp
            return ()
        if self.state is not TempleInteractionState.PRESSED or self.pressed_at is None:
            return ()

        duration = timestamp - self.pressed_at
        if not _reached_hold_threshold(duration, settings.hold_threshold):
            return ()
        self.state = TempleInteractionState.HOLDING
        return (
            _event(
                side,
                hold_start=True,
                timestamp=timestamp,
                source_sequence=source_sequence,
                duration=duration,
            ),
        )

    def _release_or_arm(
        self,
        side: HandSide,
        timestamp: float,
        source_sequence: int,
        settings: TempleGestureSettings,
        release_started_at: float | None,
    ) -> tuple[GestureEvent, ...]:
        if self.state is TempleInteractionState.WAITING_FOR_FAR:
            self.state = TempleInteractionState.IDLE
            return ()
        if self.state is TempleInteractionState.IDLE:
            return ()
        if self.state is TempleInteractionState.COOLDOWN:
            if timestamp >= self.cooldown_until:
                self.state = TempleInteractionState.IDLE
            return ()
        if self.pressed_at is None:
            self._begin_cooldown(timestamp, settings)
            return ()

        release_timestamp = timestamp if release_started_at is None else release_started_at
        duration = release_timestamp - self.pressed_at
        events: tuple[GestureEvent, ...]
        if self.state is TempleInteractionState.HOLDING:
            events = (
                _event(
                    side,
                    hold_end=True,
                    timestamp=timestamp,
                    source_sequence=source_sequence,
                    duration=duration,
                ),
            )
        elif _reached_hold_threshold(duration, settings.hold_threshold):
            events = (
                _event(
                    side,
                    hold_start=True,
                    timestamp=timestamp,
                    source_sequence=source_sequence,
                    duration=duration,
                ),
                _event(
                    side,
                    hold_end=True,
                    timestamp=timestamp,
                    source_sequence=source_sequence,
                    duration=duration,
                ),
            )
        else:
            events = (
                _event(
                    side,
                    timestamp=timestamp,
                    source_sequence=source_sequence,
                    duration=duration,
                ),
            )
        self._begin_cooldown(timestamp, settings)
        return events

    def _lose_tracking(
        self,
        side: HandSide,
        timestamp: float,
        source_sequence: int,
        settings: TempleGestureSettings,
    ) -> tuple[GestureEvent, ...]:
        if self.state is TempleInteractionState.HOLDING and self.pressed_at is not None:
            event = _event(
                side,
                hold_end=True,
                timestamp=timestamp,
                source_sequence=source_sequence,
                duration=timestamp - self.pressed_at,
            )
            self._begin_cooldown(timestamp, settings)
            return (event,)
        if self.state is TempleInteractionState.COOLDOWN:
            return ()
        self._wait_for_far()
        return ()

    def _begin_cooldown(
        self,
        timestamp: float,
        settings: TempleGestureSettings,
    ) -> None:
        self.state = TempleInteractionState.COOLDOWN
        self.pressed_at = None
        self.cooldown_until = timestamp + settings.cooldown

    def _wait_for_far(self) -> None:
        self.state = TempleInteractionState.WAITING_FOR_FAR
        self.pressed_at = None
        self.cooldown_until = 0.0


class TempleGestureDetector:
    """Convert stable per-side proximity into semantic tap/hold events only."""

    def __init__(self, settings: TempleGestureSettings | None = None) -> None:
        self.settings = settings or TempleGestureSettings()
        self._left = _SideInteraction()
        self._right = _SideInteraction()
        self._last_timestamp: float | None = None
        self._last_source_sequence: int | None = None
        self._last_expiry_timestamp: float | None = None
        self._last_arrival_timestamp: float | None = None

    @property
    def debug_state(self) -> TempleGestureDebugState:
        """Return immutable per-side interaction states."""
        return TempleGestureDebugState(self._left.state, self._right.state)

    def update(
        self,
        snapshot: TempleProximitySnapshot,
        *,
        current_timestamp: float,
    ) -> tuple[GestureEvent, ...]:
        """Consume one trusted monotonic snapshot backed by fresh capture evidence."""
        timestamp = snapshot.timestamp
        source_sequence = snapshot.source_sequence
        now = current_timestamp
        if not self._valid_input(snapshot, now):
            return ()
        assert timestamp is not None
        assert source_sequence is not None

        self._last_timestamp = timestamp
        self._last_source_sequence = source_sequence
        assert now is not None
        self._last_arrival_timestamp = now
        events: list[GestureEvent] = []
        events.extend(
            self._left.observe(
                side=HandSide.LEFT,
                proximity=snapshot.left,
                timestamp=timestamp,
                source_sequence=source_sequence,
                settings=self.settings,
                release_started_at=snapshot.left_release_started_at,
            )
        )
        events.extend(
            self._right.observe(
                side=HandSide.RIGHT,
                proximity=snapshot.right,
                timestamp=timestamp,
                source_sequence=source_sequence,
                settings=self.settings,
                release_started_at=snapshot.right_release_started_at,
            )
        )
        return tuple(events)

    def expire(self, timestamp: float) -> tuple[GestureEvent, ...]:
        """End or cancel interactions after trusted tracking loss."""
        if (
            not _is_finite_non_negative(timestamp)
            or (self._last_timestamp is not None and timestamp < self._last_timestamp)
            or (
                self._last_arrival_timestamp is not None
                and timestamp < self._last_arrival_timestamp
            )
            or (
                self._last_expiry_timestamp is not None and timestamp <= self._last_expiry_timestamp
            )
        ):
            return ()
        self._last_expiry_timestamp = timestamp
        self._last_arrival_timestamp = timestamp
        source_sequence = self._last_source_sequence or 0
        events: list[GestureEvent] = []
        events.extend(
            self._left.observe(
                side=HandSide.LEFT,
                proximity=ProximityState.UNKNOWN,
                timestamp=timestamp,
                source_sequence=source_sequence,
                settings=self.settings,
                release_started_at=None,
            )
        )
        events.extend(
            self._right.observe(
                side=HandSide.RIGHT,
                proximity=ProximityState.UNKNOWN,
                timestamp=timestamp,
                source_sequence=source_sequence,
                settings=self.settings,
                release_started_at=None,
            )
        )
        return tuple(events)

    def reset(self, timestamp: float | None = None) -> tuple[GestureEvent, ...]:
        """End active holds, clear ordering, and require a new Far baseline."""
        effective_timestamp = self._reset_timestamp(timestamp)
        source_sequence = self._last_source_sequence or 0
        events: list[GestureEvent] = []
        events.extend(
            self._left.force_reset(
                side=HandSide.LEFT,
                timestamp=effective_timestamp,
                source_sequence=source_sequence,
            )
        )
        events.extend(
            self._right.force_reset(
                side=HandSide.RIGHT,
                timestamp=effective_timestamp,
                source_sequence=source_sequence,
            )
        )
        self._last_timestamp = None
        self._last_source_sequence = None
        self._last_expiry_timestamp = None
        self._last_arrival_timestamp = None
        return tuple(events)

    def _valid_input(self, snapshot: TempleProximitySnapshot, now: float | None) -> bool:
        timestamp = snapshot.timestamp
        source_sequence = snapshot.source_sequence
        if (
            not _is_finite_non_negative(timestamp)
            or not _is_finite_non_negative(now)
            or timestamp > now
            or source_sequence is None
            or isinstance(source_sequence, bool)
            or not isinstance(source_sequence, int)
            or source_sequence < 0
            or not isinstance(snapshot.left, ProximityState)
            or not isinstance(snapshot.right, ProximityState)
            or not _valid_release_time(
                snapshot.left_release_started_at,
                timestamp,
                self._left.pressed_at,
            )
            or not _valid_release_time(
                snapshot.right_release_started_at,
                timestamp,
                self._right.pressed_at,
            )
        ):
            return False
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            return False
        if self._last_expiry_timestamp is not None and timestamp <= self._last_expiry_timestamp:
            return False
        if self._last_arrival_timestamp is not None and now < self._last_arrival_timestamp:
            return False
        return not (
            self._last_source_sequence is not None and source_sequence <= self._last_source_sequence
        )

    def _reset_timestamp(self, timestamp: float | None) -> float:
        latest_known = max(
            self._last_timestamp or 0.0,
            self._last_expiry_timestamp or 0.0,
            self._last_arrival_timestamp or 0.0,
        )
        if _is_finite_non_negative(timestamp) and timestamp >= latest_known:
            return timestamp
        return latest_known


def _is_finite_non_negative(value: object) -> TypeGuard[int | float]:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _valid_release_time(
    value: object,
    snapshot_timestamp: float,
    pressed_at: float | None,
) -> bool:
    return value is None or (
        _is_finite_non_negative(value)
        and value <= snapshot_timestamp
        and (pressed_at is None or value >= pressed_at)
    )


def _reached_hold_threshold(duration: float, threshold: float) -> bool:
    return duration >= threshold or math.isclose(
        duration,
        threshold,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def _event(
    side: HandSide,
    *,
    timestamp: float,
    source_sequence: int,
    duration: float,
    hold_start: bool = False,
    hold_end: bool = False,
) -> GestureEvent:
    if hold_start:
        event_type = (
            GestureEventType.LEFT_TEMPLE_HOLD_START
            if side is HandSide.LEFT
            else GestureEventType.RIGHT_TEMPLE_HOLD_START
        )
    elif hold_end:
        event_type = (
            GestureEventType.LEFT_TEMPLE_HOLD_END
            if side is HandSide.LEFT
            else GestureEventType.RIGHT_TEMPLE_HOLD_END
        )
    else:
        event_type = (
            GestureEventType.LEFT_TEMPLE_TAP
            if side is HandSide.LEFT
            else GestureEventType.RIGHT_TEMPLE_TAP
        )
    return GestureEvent(
        type=event_type,
        timestamp=timestamp,
        source_sequence=source_sequence,
        duration_ms=max(0.0, duration) * 1000.0,
    )
