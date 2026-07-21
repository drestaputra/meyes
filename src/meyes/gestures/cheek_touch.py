"""Framework-independent single-shot cheek-touch semantics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import HandSide
from meyes.gestures.temple_proximity import ProximityState, TempleProximitySnapshot


class CheekTouchState(StrEnum):
    """Inspectable state for one independently armed cheek interaction."""

    WAITING_FOR_FAR = "waiting_for_far"
    IDLE = "idle"
    TOUCHED = "touched"
    COOLDOWN = "cooldown"


@dataclass(frozen=True, slots=True)
class CheekTouchSettings:
    """Release-triggered touch cooldown expressed in seconds."""

    cooldown: float = 0.250

    def __post_init__(self) -> None:
        if not math.isfinite(self.cooldown) or self.cooldown < 0:
            raise ValueError("Cheek touch cooldown must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class CheekTouchDebugState:
    """Immutable state view used by deterministic diagnostics and tests."""

    left: CheekTouchState
    right: CheekTouchState


@dataclass(slots=True)
class _SideTouch:
    state: CheekTouchState = CheekTouchState.WAITING_FOR_FAR
    touched_at: float | None = None
    cooldown_until: float = 0.0

    def observe(
        self,
        *,
        side: HandSide,
        proximity: ProximityState,
        timestamp: float,
        source_sequence: int,
        cooldown: float,
        release_started_at: float | None,
    ) -> tuple[GestureEvent, ...]:
        if proximity is ProximityState.UNKNOWN:
            self.reset()
            return ()
        if self.state is CheekTouchState.WAITING_FOR_FAR:
            if proximity is ProximityState.FAR:
                self.state = CheekTouchState.IDLE
            return ()
        if self.state is CheekTouchState.COOLDOWN:
            if proximity is ProximityState.FAR and timestamp >= self.cooldown_until:
                self.state = CheekTouchState.IDLE
            return ()
        if self.state is CheekTouchState.IDLE:
            if proximity is ProximityState.NEAR and release_started_at is None:
                self.state = CheekTouchState.TOUCHED
                self.touched_at = timestamp
            return ()
        if proximity is not ProximityState.FAR or self.touched_at is None:
            return ()

        released_at = timestamp if release_started_at is None else release_started_at
        duration = max(0.0, released_at - self.touched_at)
        self.state = CheekTouchState.COOLDOWN
        self.touched_at = None
        self.cooldown_until = timestamp + cooldown
        event_type = (
            GestureEventType.LEFT_CHEEK_TOUCH
            if side is HandSide.LEFT
            else GestureEventType.RIGHT_CHEEK_TOUCH
        )
        return (
            GestureEvent(
                event_type,
                timestamp=timestamp,
                source_sequence=source_sequence,
                duration_ms=duration * 1000.0,
            ),
        )

    def reset(self) -> None:
        self.state = CheekTouchState.WAITING_FOR_FAR
        self.touched_at = None
        self.cooldown_until = 0.0


class CheekTouchDetector:
    """Emit one side-specific event only after a stable cheek touch is released."""

    def __init__(self, settings: CheekTouchSettings | None = None) -> None:
        self.settings = settings or CheekTouchSettings()
        self._left = _SideTouch()
        self._right = _SideTouch()

    @property
    def debug_state(self) -> CheekTouchDebugState:
        """Expose immutable state without allowing mutation of detector internals."""
        return CheekTouchDebugState(self._left.state, self._right.state)

    def update(self, snapshot: TempleProximitySnapshot) -> tuple[GestureEvent, ...]:
        """Consume one stabilized cheek proximity snapshot."""
        if not isinstance(snapshot, TempleProximitySnapshot):
            raise TypeError("Expected TempleProximitySnapshot")
        timestamp = snapshot.timestamp
        source_sequence = snapshot.source_sequence
        if (
            timestamp is None
            or source_sequence is None
            or not math.isfinite(timestamp)
            or timestamp < 0
            or isinstance(source_sequence, bool)
            or source_sequence < 0
        ):
            self.reset()
            return ()
        events = self._left.observe(
            side=HandSide.LEFT,
            proximity=snapshot.left,
            timestamp=timestamp,
            source_sequence=source_sequence,
            cooldown=self.settings.cooldown,
            release_started_at=snapshot.left_release_started_at,
        )
        events += self._right.observe(
            side=HandSide.RIGHT,
            proximity=snapshot.right,
            timestamp=timestamp,
            source_sequence=source_sequence,
            cooldown=self.settings.cooldown,
            release_started_at=snapshot.right_release_started_at,
        )
        return events

    def reset(self) -> None:
        """Require fresh Far evidence before either cheek can trigger again."""
        self._left.reset()
        self._right.reset()
