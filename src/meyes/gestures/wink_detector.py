"""Independent wink detection with blink suppression and cooldown."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import FaceObservation


class EyeState(StrEnum):
    """Hysteretic eye state derived from normalized openness."""

    UNKNOWN = "unknown"
    OPEN = "open"
    CLOSED = "closed"


class EyeSide(StrEnum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class WinkDetectorSettings:
    """Timing and openness thresholds expressed in seconds/scores."""

    closed_threshold: float = 0.35
    open_threshold: float = 0.65
    min_duration: float = 0.140
    max_duration: float = 0.900
    cooldown: float = 0.350
    both_eye_sync_window: float = 0.090
    tracking_timeout: float = 0.250

    def __post_init__(self) -> None:
        if not 0.0 <= self.closed_threshold < self.open_threshold <= 1.0:
            raise ValueError("Eye thresholds must satisfy 0 <= closed < open <= 1")
        if not 0 < self.min_duration < self.max_duration:
            raise ValueError("Wink duration must satisfy 0 < min < max")
        if self.cooldown < 0 or self.both_eye_sync_window < 0 or self.tracking_timeout <= 0:
            raise ValueError("Wink timing values must be non-negative and timeout positive")


@dataclass(slots=True)
class _WinkCandidate:
    side: EyeSide
    started_at: float
    eligible: bool
    emitted: bool = False


@dataclass(frozen=True, slots=True)
class WinkDebugState:
    """Inspectable state for diagnostics without exposing mutable internals."""

    left_eye: EyeState
    right_eye: EyeState
    candidate: EyeSide | None
    blink_suppressed: bool
    cooldown_until: float


class WinkDetector:
    """Convert independent eye openness into at-most-once wink events."""

    def __init__(self, settings: WinkDetectorSettings | None = None) -> None:
        self.settings = settings or WinkDetectorSettings()
        self._left_state = EyeState.UNKNOWN
        self._right_state = EyeState.UNKNOWN
        self._candidate: _WinkCandidate | None = None
        self._last_timestamp: float | None = None
        self._last_valid_timestamp: float | None = None
        self._last_left_close_at: float | None = None
        self._last_right_close_at: float | None = None
        self._blink_suppressed = False
        self._cooldown_until = 0.0

    @property
    def debug_state(self) -> WinkDebugState:
        """Return a stable snapshot for diagnostics."""
        return WinkDebugState(
            left_eye=self._left_state,
            right_eye=self._right_state,
            candidate=self._candidate.side if self._candidate else None,
            blink_suppressed=self._blink_suppressed,
            cooldown_until=self._cooldown_until,
        )

    def update(self, observation: FaceObservation) -> tuple[GestureEvent, ...]:
        """Consume one monotonic face observation and emit zero or one event."""
        timestamp = observation.capture_timestamp
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            return ()
        self._last_timestamp = timestamp

        if (
            self._last_valid_timestamp is not None
            and timestamp - self._last_valid_timestamp > self.settings.tracking_timeout
        ):
            self._reset_transient_eye_state()

        if (
            not observation.face_detected
            or observation.left_eye_openness is None
            or observation.right_eye_openness is None
        ):
            self._reset_transient_eye_state()
            return ()

        self._last_valid_timestamp = timestamp
        previous_left = self._left_state
        previous_right = self._right_state
        self._left_state = self._classify(observation.left_eye_openness, self._left_state)
        self._right_state = self._classify(observation.right_eye_openness, self._right_state)

        left_just_closed = (
            self._left_state is EyeState.CLOSED and previous_left is not EyeState.CLOSED
        )
        right_just_closed = (
            self._right_state is EyeState.CLOSED and previous_right is not EyeState.CLOSED
        )
        if left_just_closed:
            self._last_left_close_at = timestamp
        if right_just_closed:
            self._last_right_close_at = timestamp

        if self._is_synchronized_blink():
            self._blink_suppressed = True
            self._candidate = None

        if self._left_state is EyeState.OPEN and self._right_state is EyeState.OPEN:
            self._blink_suppressed = False
            self._candidate = None
            return ()

        if self._left_state is EyeState.CLOSED and self._right_state is EyeState.CLOSED:
            self._blink_suppressed = True
            self._candidate = None
            return ()

        if self._blink_suppressed:
            self._candidate = None
            return ()

        side = self._exclusive_closed_side()
        if side is None:
            self._candidate = None
            return ()

        if self._candidate is None or self._candidate.side is not side:
            self._candidate = _WinkCandidate(
                side=side,
                started_at=timestamp,
                eligible=timestamp >= self._cooldown_until,
            )
            return ()

        candidate = self._candidate
        duration = timestamp - candidate.started_at
        if candidate.emitted or not candidate.eligible:
            return ()
        if duration > self.settings.max_duration:
            candidate.eligible = False
            return ()
        if duration < self.settings.min_duration:
            return ()

        candidate.emitted = True
        self._cooldown_until = timestamp + self.settings.cooldown
        event_type = (
            GestureEventType.LEFT_WINK if side is EyeSide.LEFT else GestureEventType.RIGHT_WINK
        )
        return (
            GestureEvent(
                type=event_type,
                timestamp=timestamp,
                source_sequence=observation.source_sequence,
                duration_ms=duration * 1000.0,
            ),
        )

    def reset(self) -> None:
        """Reset all state, including cooldown, for tracking restart."""
        self._left_state = EyeState.UNKNOWN
        self._right_state = EyeState.UNKNOWN
        self._candidate = None
        self._last_timestamp = None
        self._last_valid_timestamp = None
        self._last_left_close_at = None
        self._last_right_close_at = None
        self._blink_suppressed = False
        self._cooldown_until = 0.0

    def _classify(self, openness: float, previous: EyeState) -> EyeState:
        if openness <= self.settings.closed_threshold:
            return EyeState.CLOSED
        if openness >= self.settings.open_threshold:
            return EyeState.OPEN
        return previous

    def _is_synchronized_blink(self) -> bool:
        if self._last_left_close_at is None or self._last_right_close_at is None:
            return False
        difference = abs(self._last_left_close_at - self._last_right_close_at)
        return difference <= self.settings.both_eye_sync_window

    def _exclusive_closed_side(self) -> EyeSide | None:
        if self._left_state is EyeState.CLOSED and self._right_state is EyeState.OPEN:
            return EyeSide.LEFT
        if self._right_state is EyeState.CLOSED and self._left_state is EyeState.OPEN:
            return EyeSide.RIGHT
        return None

    def _reset_transient_eye_state(self) -> None:
        self._left_state = EyeState.UNKNOWN
        self._right_state = EyeState.UNKNOWN
        self._candidate = None
        self._last_valid_timestamp = None
        self._blink_suppressed = False
