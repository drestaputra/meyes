"""Framework-independent per-side temple proximity hysteresis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from meyes.config.models import GestureSettings
from meyes.domain.observations import (
    HandSide,
    TempleFeatureObservation,
    TempleFeatureStatus,
)


class ProximityState(StrEnum):
    """Stable proximity state for one anatomical temple."""

    UNKNOWN = "unknown"
    FAR = "far"
    NEAR = "near"


@dataclass(frozen=True, slots=True)
class TempleProximitySettings:
    """Distance thresholds and timing expressed as ratios/seconds."""

    enter_ratio: float = 0.075
    exit_ratio: float = 0.095
    stabilization: float = 0.180
    tracking_timeout: float = 0.250

    def __post_init__(self) -> None:
        if not all(math.isfinite(value) for value in (self.enter_ratio, self.exit_ratio)):
            raise ValueError("Temple proximity thresholds must be finite")
        if not 0.0 <= self.enter_ratio < self.exit_ratio:
            raise ValueError("Temple thresholds must satisfy 0 <= enter < exit")
        if not math.isfinite(self.stabilization) or self.stabilization < 0:
            raise ValueError("Temple stabilization must be finite and non-negative")
        if not math.isfinite(self.tracking_timeout) or self.tracking_timeout <= 0:
            raise ValueError("Temple tracking timeout must be finite and positive")

    @classmethod
    def from_settings(cls, settings: GestureSettings) -> TempleProximitySettings:
        """Convert persisted millisecond settings into detector units."""
        return cls(
            enter_ratio=settings.temple_enter_ratio,
            exit_ratio=settings.temple_exit_ratio,
            stabilization=settings.temple_stabilization_ms / 1000.0,
            tracking_timeout=settings.tracking_timeout_ms / 1000.0,
        )


@dataclass(frozen=True, slots=True)
class TempleProximitySnapshot:
    """Immutable left/right state snapshot for diagnostics and composition."""

    source_sequence: int | None
    timestamp: float | None
    left: ProximityState
    right: ProximityState
    left_release_started_at: float | None = None
    right_release_started_at: float | None = None

    def state(self, side: HandSide) -> ProximityState:
        """Return one anatomical side, failing closed for an unknown side."""
        if side is HandSide.LEFT:
            return self.left
        if side is HandSide.RIGHT:
            return self.right
        return ProximityState.UNKNOWN

    def release_started_at(self, side: HandSide) -> float | None:
        """Return raw Far-candidate onset while stable release is pending or completes."""
        if side is HandSide.LEFT:
            return self.left_release_started_at
        if side is HandSide.RIGHT:
            return self.right_release_started_at
        return None


@dataclass(frozen=True, slots=True)
class _CompletedTransition:
    target: ProximityState
    started_at: float


@dataclass(slots=True)
class _SideTracker:
    state: ProximityState = ProximityState.UNKNOWN
    candidate: ProximityState | None = None
    candidate_started_at: float | None = None

    def observe(
        self,
        distance_ratio: float | None,
        timestamp: float,
        settings: TempleProximitySettings,
    ) -> _CompletedTransition | None:
        if self.state is ProximityState.NEAR:
            should_release = distance_ratio is None or distance_ratio >= settings.exit_ratio
            if should_release:
                return self._stabilize(
                    ProximityState.FAR,
                    timestamp,
                    settings.stabilization,
                )
            else:
                self.cancel_candidate()
            return None

        should_enter = distance_ratio is not None and distance_ratio <= settings.enter_ratio
        if should_enter:
            return self._stabilize(
                ProximityState.NEAR,
                timestamp,
                settings.stabilization,
            )

        self.state = ProximityState.FAR
        self.cancel_candidate()
        return None

    def cancel_candidate(self) -> None:
        self.candidate = None
        self.candidate_started_at = None

    def reset(self) -> None:
        self.state = ProximityState.UNKNOWN
        self.cancel_candidate()

    def _stabilize(
        self,
        target: ProximityState,
        timestamp: float,
        duration: float,
    ) -> _CompletedTransition | None:
        if self.candidate is not target or self.candidate_started_at is None:
            self.candidate = target
            self.candidate_started_at = timestamp
            return None
        if (
            timestamp > self.candidate_started_at
            and timestamp - self.candidate_started_at >= duration
        ):
            started_at = self.candidate_started_at
            self.state = target
            self.cancel_candidate()
            return _CompletedTransition(target, started_at)
        return None


class TempleProximityDetector:
    """Stabilize independent left/right temple distance classifications."""

    def __init__(self, settings: TempleProximitySettings | None = None) -> None:
        self.settings = settings or TempleProximitySettings()
        self._left = _SideTracker()
        self._right = _SideTracker()
        self._last_valid_sequence: int | None = None
        self._last_valid_capture_timestamp: float | None = None
        self._last_valid_processed_timestamp: float | None = None
        self._last_valid_evidence_timestamp: float | None = None
        self._snapshot = TempleProximitySnapshot(
            source_sequence=None,
            timestamp=None,
            left=ProximityState.UNKNOWN,
            right=ProximityState.UNKNOWN,
        )

    @property
    def snapshot(self) -> TempleProximitySnapshot:
        """Return the current immutable stable state."""
        return self._snapshot

    def update(self, observation: TempleFeatureObservation) -> TempleProximitySnapshot:
        """Consume one feature observation without emitting semantic actions."""
        if observation.status is TempleFeatureStatus.EXPIRED:
            if self._valid_expiry(observation):
                self._expire(observation.source_sequence, observation.processed_timestamp)
            return self._snapshot

        ratios = self._valid_ratios(observation)
        if ratios is None:
            self._cancel_candidates()
            return self.poll(observation.processed_timestamp)

        if self._is_duplicate_or_regressing(observation):
            return self.poll(observation.processed_timestamp)

        now = observation.processed_timestamp
        self.poll(now)
        evidence_timestamp = observation.capture_timestamp
        evidence_age = now - evidence_timestamp
        if evidence_age < 0 or evidence_age > self.settings.tracking_timeout:
            self._cancel_candidates()
            return self._snapshot

        self._last_valid_sequence = observation.source_sequence
        self._last_valid_capture_timestamp = observation.capture_timestamp
        self._last_valid_processed_timestamp = observation.processed_timestamp
        self._last_valid_evidence_timestamp = evidence_timestamp

        left_transition = self._left.observe(
            ratios.get(HandSide.LEFT),
            evidence_timestamp,
            self.settings,
        )
        right_transition = self._right.observe(
            ratios.get(HandSide.RIGHT),
            evidence_timestamp,
            self.settings,
        )
        self._publish(
            observation.source_sequence,
            evidence_timestamp,
            left_release_started_at=_release_started_at(self._left, left_transition),
            right_release_started_at=_release_started_at(self._right, right_transition),
        )
        return self._snapshot

    def poll(self, timestamp: float) -> TempleProximitySnapshot:
        """Expire stale state when no new feature observation is available."""
        if not math.isfinite(timestamp) or (
            self._last_valid_processed_timestamp is not None
            and timestamp < self._last_valid_processed_timestamp
        ):
            return self._snapshot
        if self._expire_if_timed_out(timestamp):
            self._publish(self._snapshot.source_sequence, timestamp)
        return self._snapshot

    def reset(self) -> None:
        """Clear stable states, candidates, freshness, and ordering history."""
        self._left.reset()
        self._right.reset()
        self._last_valid_sequence = None
        self._last_valid_capture_timestamp = None
        self._last_valid_processed_timestamp = None
        self._last_valid_evidence_timestamp = None
        self._snapshot = TempleProximitySnapshot(
            source_sequence=None,
            timestamp=None,
            left=ProximityState.UNKNOWN,
            right=ProximityState.UNKNOWN,
        )

    def _valid_ratios(
        self,
        observation: TempleFeatureObservation,
    ) -> dict[HandSide, float] | None:
        if observation.status not in {
            TempleFeatureStatus.READY,
            TempleFeatureStatus.NO_ELIGIBLE_HANDS,
        }:
            return None
        if not (
            math.isfinite(observation.capture_timestamp)
            and math.isfinite(observation.processed_timestamp)
            and observation.processed_timestamp >= observation.capture_timestamp
        ):
            return None
        if observation.status is TempleFeatureStatus.NO_ELIGIBLE_HANDS and observation.proximities:
            return None

        ratios: dict[HandSide, float] = {}
        for proximity in observation.proximities:
            if (
                proximity.side not in {HandSide.LEFT, HandSide.RIGHT}
                or proximity.side in ratios
                or not math.isfinite(proximity.distance_ratio)
                or proximity.distance_ratio < 0
            ):
                return None
            ratios[proximity.side] = proximity.distance_ratio
        return ratios

    def _is_duplicate_or_regressing(self, observation: TempleFeatureObservation) -> bool:
        return (
            (
                self._last_valid_sequence is not None
                and observation.source_sequence <= self._last_valid_sequence
            )
            or (
                self._last_valid_capture_timestamp is not None
                and observation.capture_timestamp <= self._last_valid_capture_timestamp
            )
            or (
                self._last_valid_processed_timestamp is not None
                and observation.processed_timestamp < self._last_valid_processed_timestamp
            )
        )

    def _valid_expiry(self, observation: TempleFeatureObservation) -> bool:
        timestamp = observation.processed_timestamp
        source_sequence = observation.source_sequence
        return (
            isinstance(timestamp, (int, float))
            and not isinstance(timestamp, bool)
            and math.isfinite(timestamp)
            and timestamp >= 0
            and isinstance(source_sequence, int)
            and not isinstance(source_sequence, bool)
            and source_sequence >= 0
            and (
                self._last_valid_evidence_timestamp is None
                or timestamp >= self._last_valid_evidence_timestamp
            )
            and (
                self._last_valid_processed_timestamp is None
                or timestamp >= self._last_valid_processed_timestamp
            )
            and (self._last_valid_sequence is None or source_sequence >= self._last_valid_sequence)
        )

    def _cancel_candidates(self) -> None:
        self._left.cancel_candidate()
        self._right.cancel_candidate()

    def _expire_if_timed_out(self, timestamp: float) -> bool:
        if (
            self._last_valid_evidence_timestamp is None
            or timestamp - self._last_valid_evidence_timestamp <= self.settings.tracking_timeout
        ):
            return False
        self._left.reset()
        self._right.reset()
        self._last_valid_evidence_timestamp = None
        return True

    def _expire(self, source_sequence: int | None, timestamp: float) -> None:
        self._left.reset()
        self._right.reset()
        self._last_valid_evidence_timestamp = None
        self._publish(source_sequence, timestamp if math.isfinite(timestamp) else None)

    def _publish(
        self,
        source_sequence: int | None,
        timestamp: float | None,
        *,
        left_release_started_at: float | None = None,
        right_release_started_at: float | None = None,
    ) -> None:
        self._snapshot = TempleProximitySnapshot(
            source_sequence=source_sequence,
            timestamp=timestamp,
            left=self._left.state,
            right=self._right.state,
            left_release_started_at=left_release_started_at,
            right_release_started_at=right_release_started_at,
        )


def _release_started_at(
    tracker: _SideTracker,
    completed: _CompletedTransition | None,
) -> float | None:
    if completed is not None and completed.target is ProximityState.FAR:
        return completed.started_at
    if tracker.candidate is ProximityState.FAR:
        return tracker.candidate_started_at
    return None
