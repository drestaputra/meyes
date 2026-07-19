"""Central semantic gesture engine."""

from __future__ import annotations

from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent
from meyes.domain.observations import FaceObservation
from meyes.gestures.wink_detector import WinkDetector, WinkDetectorSettings


class GestureEngine:
    """Route normalized observations through gesture state machines."""

    def __init__(self, wink_detector: WinkDetector | None = None) -> None:
        self.wink_detector = wink_detector or WinkDetector()

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
        return cls(WinkDetector(wink_settings))

    def update_face(self, observation: FaceObservation) -> tuple[GestureEvent, ...]:
        """Emit face-derived semantic events with no binding side effects."""
        return self.wink_detector.update(observation)

    def reset(self) -> None:
        """Reset all gesture state during pause, failure, or shutdown."""
        self.wink_detector.reset()
