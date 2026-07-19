"""Central semantic gesture engine."""

from __future__ import annotations

from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent
from meyes.domain.observations import FaceObservation, TempleFeatureObservation
from meyes.gestures.temple_proximity import (
    TempleProximityDetector,
    TempleProximitySettings,
    TempleProximitySnapshot,
)
from meyes.gestures.wink_detector import WinkDetector, WinkDetectorSettings


class GestureEngine:
    """Route normalized observations through gesture state machines."""

    def __init__(
        self,
        wink_detector: WinkDetector | None = None,
        temple_proximity_detector: TempleProximityDetector | None = None,
    ) -> None:
        self.wink_detector = wink_detector or WinkDetector()
        self.temple_proximity_detector = temple_proximity_detector or TempleProximityDetector()

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
        return cls(
            WinkDetector(wink_settings),
            TempleProximityDetector(temple_settings),
        )

    def update_face(self, observation: FaceObservation) -> tuple[GestureEvent, ...]:
        """Emit face-derived semantic events with no binding side effects."""
        return self.wink_detector.update(observation)

    def update_temple(
        self,
        observation: TempleFeatureObservation,
    ) -> TempleProximitySnapshot | None:
        """Return a snapshot only when a temple proximity state changes."""
        previous = self.temple_proximity_detector.snapshot
        current = self.temple_proximity_detector.update(observation)
        return current if _proximity_states_changed(previous, current) else None

    def poll_temple(self, timestamp: float) -> TempleProximitySnapshot | None:
        """Expire temple state independently of the latest raw feature status."""
        previous = self.temple_proximity_detector.snapshot
        current = self.temple_proximity_detector.poll(timestamp)
        return current if _proximity_states_changed(previous, current) else None

    def reset_face(self) -> None:
        """Reset only face-derived state after a stale face observation."""
        self.wink_detector.reset()

    def reset(self) -> None:
        """Reset all gesture state during pause, failure, or shutdown."""
        self.reset_face()
        self.temple_proximity_detector.reset()


def _proximity_states_changed(
    previous: TempleProximitySnapshot,
    current: TempleProximitySnapshot,
) -> bool:
    """Ignore timestamp-only snapshot refreshes at the controller boundary."""
    return previous.left is not current.left or previous.right is not current.right
