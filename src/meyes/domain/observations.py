"""Normalized observations emitted by computer-vision adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NormalizedPoint:
    """One landmark in normalized image coordinates."""

    x: float
    y: float
    z: float = 0.0


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
