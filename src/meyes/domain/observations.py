"""Normalized observations emitted by computer-vision adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class NormalizedPoint:
    """One landmark in normalized image coordinates."""

    x: float
    y: float
    z: float = 0.0


class HandSide(StrEnum):
    """Anatomical hand side after input orientation normalization."""

    LEFT = "left"
    RIGHT = "right"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DetectedHand:
    """One hand in canonical, unmirrored processing coordinates."""

    side: HandSide
    confidence: float | None
    landmarks: tuple[NormalizedPoint, ...]

    def landmark(self, index: int) -> NormalizedPoint | None:
        """Return a landmark when the model supplied the requested index."""
        if index < 0 or index >= len(self.landmarks):
            return None
        return self.landmarks[index]


@dataclass(frozen=True, slots=True)
class HandObservation:
    """All normalized hands detected in one camera frame."""

    source_sequence: int
    capture_timestamp: float
    processed_timestamp: float
    hands: tuple[DetectedHand, ...] = ()

    @property
    def hand_detected(self) -> bool:
        """Return whether at least one hand was detected."""
        return bool(self.hands)

    @property
    def processing_latency_ms(self) -> float:
        """Return capture-to-observation latency in milliseconds."""
        return max(0.0, (self.processed_timestamp - self.capture_timestamp) * 1000.0)

    def hand(self, side: HandSide) -> DetectedHand | None:
        """Return the highest-confidence detection for one anatomical side."""
        candidates = [item for item in self.hands if item.side is side]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.confidence or 0.0)


@dataclass(frozen=True, slots=True)
class FaceObservation:
    """Face and independent eye features for gesture consumers."""

    source_sequence: int
    capture_timestamp: float
    processed_timestamp: float
    face_detected: bool
    confidence: float | None = None
    left_eye_openness: float | None = None
    right_eye_openness: float | None = None
    left_iris_center: NormalizedPoint | None = None
    right_iris_center: NormalizedPoint | None = None
    landmarks: tuple[NormalizedPoint, ...] = ()

    @property
    def processing_latency_ms(self) -> float:
        """Return capture-to-observation latency in milliseconds."""
        return max(0.0, (self.processed_timestamp - self.capture_timestamp) * 1000.0)
