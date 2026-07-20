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
    frame_width: int = 0
    frame_height: int = 0

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
    frame_width: int = 0
    frame_height: int = 0

    @property
    def processing_latency_ms(self) -> float:
        """Return capture-to-observation latency in milliseconds."""
        return max(0.0, (self.processed_timestamp - self.capture_timestamp) * 1000.0)


class GazeFeatureStatus(StrEnum):
    """Availability state for one uncalibrated eye-relative gaze feature."""

    READY = "ready"
    FACE_NOT_DETECTED = "face_not_detected"
    EYE_OPENNESS_UNAVAILABLE = "eye_openness_unavailable"
    EYES_CLOSED = "eyes_closed"
    LANDMARKS_UNAVAILABLE = "landmarks_unavailable"
    INVALID_GEOMETRY = "invalid_geometry"
    INVALID_TIME = "invalid_time"


@dataclass(frozen=True, slots=True)
class GazeFeatureVector:
    """Iris position relative to one eye-local horizontal and vertical axis."""

    horizontal: float
    vertical: float


@dataclass(frozen=True, slots=True)
class GazeFeatureObservation:
    """Uncalibrated binocular gaze features derived from one face observation."""

    source_sequence: int
    capture_timestamp: float
    processed_timestamp: float
    status: GazeFeatureStatus
    left_eye: GazeFeatureVector | None = None
    right_eye: GazeFeatureVector | None = None
    combined: GazeFeatureVector | None = None
    face_confidence: float | None = None

    @property
    def ready(self) -> bool:
        """Return whether a complete binocular feature is available for calibration."""
        return self.status is GazeFeatureStatus.READY and self.combined is not None


class TempleFeatureStatus(StrEnum):
    """Availability state for one paired temple-feature observation."""

    READY = "ready"
    NO_ELIGIBLE_HANDS = "no_eligible_hands"
    FACE_NOT_DETECTED = "face_not_detected"
    FACE_UNAVAILABLE = "face_unavailable"
    HAND_STALE = "hand_stale"
    PAIR_SKEW = "pair_skew"
    INVALID_GEOMETRY = "invalid_geometry"
    INVALID_TIME = "invalid_time"
    OUT_OF_ORDER = "out_of_order"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class TempleProximity:
    """One same-side fingertip distance normalized by face width."""

    side: HandSide
    distance_ratio: float
    hand_confidence: float


@dataclass(frozen=True, slots=True)
class TempleFeatureObservation:
    """Result of freshness pairing and anatomical temple feature extraction."""

    source_sequence: int
    capture_timestamp: float
    processed_timestamp: float
    status: TempleFeatureStatus
    face_source_sequence: int | None = None
    face_capture_timestamp: float | None = None
    pair_skew_ms: float | None = None
    proximities: tuple[TempleProximity, ...] = ()

    @property
    def valid_pair(self) -> bool:
        """Return whether face/hand timing and face geometry were valid."""
        return self.status in {
            TempleFeatureStatus.READY,
            TempleFeatureStatus.NO_ELIGIBLE_HANDS,
        }

    def proximity(self, side: HandSide) -> TempleProximity | None:
        """Return the feature for one anatomical side when available."""
        return next((item for item in self.proximities if item.side is side), None)
