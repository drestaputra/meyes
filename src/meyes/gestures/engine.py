"""Central semantic gesture engine."""

from __future__ import annotations

from dataclasses import dataclass

from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent
from meyes.domain.observations import (
    FaceObservation,
    TempleFeatureObservation,
    TempleFeatureStatus,
)
from meyes.gestures.temple_gestures import TempleGestureDetector, TempleGestureSettings
from meyes.gestures.temple_proximity import (
    ProximityState,
    TempleProximityDetector,
    TempleProximitySettings,
    TempleProximitySnapshot,
)
from meyes.gestures.wink_detector import WinkDetector, WinkDetectorSettings


@dataclass(frozen=True, slots=True)
class TempleUpdateResult:
    """One atomic temple update for controller-side publication."""

    proximity: TempleProximitySnapshot | None = None
    events: tuple[GestureEvent, ...] = ()


class GestureEngine:
    """Route normalized observations through gesture state machines."""

    def __init__(
        self,
        wink_detector: WinkDetector | None = None,
        temple_proximity_detector: TempleProximityDetector | None = None,
        temple_gesture_detector: TempleGestureDetector | None = None,
    ) -> None:
        self.wink_detector = wink_detector or WinkDetector()
        self.temple_proximity_detector = temple_proximity_detector or TempleProximityDetector()
        self.temple_gesture_detector = temple_gesture_detector or TempleGestureDetector()

    @classmethod
    def from_settings(cls, settings: GestureSettings) -> GestureEngine:
        """Convert persisted millisecond settings at the composition boundary."""
        wink_settings = WinkDetectorSettings(
            closed_threshold=settings.wink_closed_threshold,
            open_threshold=settings.wink_open_threshold,
            min_duration=settings.wink_min_duration_ms / 1000.0,
            max_duration=settings.wink_max_duration_ms / 1000.0,
            cooldown=settings.wink_cooldown_ms / 1000.0,
            both_eye_sync_window=settings.both_eye_sync_window_ms / 1000.0,
            tracking_timeout=settings.tracking_timeout_ms / 1000.0,
        )
        temple_settings = TempleProximitySettings.from_settings(settings)
        temple_gesture_settings = TempleGestureSettings.from_settings(settings)
        return cls(
            WinkDetector(wink_settings),
            TempleProximityDetector(temple_settings),
            TempleGestureDetector(temple_gesture_settings),
        )

    def update_face(self, observation: FaceObservation) -> tuple[GestureEvent, ...]:
        """Emit face-derived semantic events with no binding side effects."""
        return self.wink_detector.update(observation)

    def update_temple(
        self,
        observation: TempleFeatureObservation,
    ) -> TempleUpdateResult:
        """Derive proximity transitions and semantic events atomically."""
        previous = self.temple_proximity_detector.snapshot
        before_evidence = self.temple_proximity_detector.poll(observation.processed_timestamp)
        events: list[GestureEvent] = []
        if _became_unknown(previous, before_evidence):
            events.extend(
                self.temple_gesture_detector.expire(
                    _snapshot_time(before_evidence, observation.processed_timestamp)
                )
            )
        current = self.temple_proximity_detector.update(observation)
        if _is_accepted_evidence(observation, current):
            events.extend(
                self.temple_gesture_detector.update(
                    current,
                    current_timestamp=observation.processed_timestamp,
                )
            )
        elif _became_unknown(before_evidence, current):
            events.extend(
                self.temple_gesture_detector.expire(
                    _snapshot_time(current, observation.processed_timestamp)
                )
            )
        proximity = current if _proximity_states_changed(previous, current) else None
        return TempleUpdateResult(proximity, tuple(events))

    def poll_temple(self, timestamp: float) -> TempleUpdateResult:
        """Expire temple state independently of the latest raw feature status."""
        previous = self.temple_proximity_detector.snapshot
        current = self.temple_proximity_detector.poll(timestamp)
        changed = _proximity_states_changed(previous, current)
        events = self.temple_gesture_detector.expire(timestamp) if changed else ()
        return TempleUpdateResult(current if changed else None, events)

    def reset_face(self) -> None:
        """Reset only face-derived state after a stale face observation."""
        self.wink_detector.reset()

    def reset(self, timestamp: float | None = None) -> tuple[GestureEvent, ...]:
        """End active holds, then reset all state during lifecycle changes."""
        self.reset_face()
        events = self.temple_gesture_detector.reset(timestamp)
        self.temple_proximity_detector.reset()
        return events


def _proximity_states_changed(
    previous: TempleProximitySnapshot,
    current: TempleProximitySnapshot,
) -> bool:
    """Ignore timestamp-only snapshot refreshes at the controller boundary."""
    return previous.left is not current.left or previous.right is not current.right


def _is_accepted_evidence(
    observation: TempleFeatureObservation,
    snapshot: TempleProximitySnapshot,
) -> bool:
    return (
        observation.status in {TempleFeatureStatus.READY, TempleFeatureStatus.NO_ELIGIBLE_HANDS}
        and snapshot.source_sequence == observation.source_sequence
        and snapshot.timestamp == observation.capture_timestamp
    )


def _became_unknown(
    previous: TempleProximitySnapshot,
    current: TempleProximitySnapshot,
) -> bool:
    return _proximity_states_changed(previous, current) and (
        current.left is ProximityState.UNKNOWN or current.right is ProximityState.UNKNOWN
    )


def _snapshot_time(snapshot: TempleProximitySnapshot, fallback: float) -> float:
    return snapshot.timestamp if snapshot.timestamp is not None else fallback
