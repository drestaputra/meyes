"""Fail-closed, eye-relative gaze feature extraction."""

from __future__ import annotations

import math
from typing import TypeGuard

from meyes.domain.observations import (
    FaceObservation,
    GazeFeatureObservation,
    GazeFeatureStatus,
    GazeFeatureVector,
    NormalizedPoint,
)

# MediaPipe Face Landmarker topology. Corners are ordered from image-left to
# image-right in canonical, unmirrored processing coordinates.
LEFT_EYE_CORNERS = (362, 263)
LEFT_EYE_VERTICAL = (386, 374)
RIGHT_EYE_CORNERS = (33, 133)
RIGHT_EYE_VERTICAL = (159, 145)

MINIMUM_EYE_AXIS_PIXELS = 1.0
DEFAULT_MINIMUM_EYE_OPENNESS = 0.35


def extract_gaze_features(
    face: FaceObservation,
    *,
    processed_timestamp: float,
    minimum_eye_openness: float = DEFAULT_MINIMUM_EYE_OPENNESS,
) -> GazeFeatureObservation:
    """Extract binocular iris ratios without mapping them to a screen position."""
    if not isinstance(face, FaceObservation):
        raise TypeError("Expected FaceObservation")
    if not _finite_number(minimum_eye_openness) or not 0.0 <= minimum_eye_openness <= 1.0:
        raise ValueError("Minimum eye openness must be finite and within 0..1")
    if not _valid_time(face, processed_timestamp):
        return _result(face, GazeFeatureStatus.INVALID_TIME, processed_timestamp)
    face_detected: object = face.face_detected
    if not isinstance(face_detected, bool):
        return _result(face, GazeFeatureStatus.INVALID_GEOMETRY, processed_timestamp)
    if not face_detected:
        return _result(face, GazeFeatureStatus.FACE_NOT_DETECTED, processed_timestamp)
    if face.confidence is not None and (
        not _finite_number(face.confidence) or not 0.0 <= face.confidence <= 1.0
    ):
        return _result(face, GazeFeatureStatus.INVALID_GEOMETRY, processed_timestamp)

    openness = (face.left_eye_openness, face.right_eye_openness)
    if any(value is None for value in openness):
        return _result(face, GazeFeatureStatus.EYE_OPENNESS_UNAVAILABLE, processed_timestamp)
    if not all(
        value is not None and _finite_number(value) and 0.0 <= value <= 1.0 for value in openness
    ):
        return _result(face, GazeFeatureStatus.INVALID_GEOMETRY, processed_timestamp)
    if any(value is not None and value < minimum_eye_openness for value in openness):
        return _result(face, GazeFeatureStatus.EYES_CLOSED, processed_timestamp)

    required_indices = (
        *LEFT_EYE_CORNERS,
        *LEFT_EYE_VERTICAL,
        *RIGHT_EYE_CORNERS,
        *RIGHT_EYE_VERTICAL,
    )
    if (
        not isinstance(face.landmarks, tuple)
        or not isinstance(face.left_iris_center, NormalizedPoint)
        or not isinstance(face.right_iris_center, NormalizedPoint)
        or len(face.landmarks) <= max(required_indices)
    ):
        return _result(face, GazeFeatureStatus.LANDMARKS_UNAVAILABLE, processed_timestamp)
    if (
        not isinstance(face.frame_width, int)
        or isinstance(face.frame_width, bool)
        or not isinstance(face.frame_height, int)
        or isinstance(face.frame_height, bool)
        or face.frame_width <= 0
        or face.frame_height <= 0
    ):
        return _result(face, GazeFeatureStatus.INVALID_GEOMETRY, processed_timestamp)

    required_points = [face.landmarks[index] for index in required_indices]
    required_points.extend((face.left_iris_center, face.right_iris_center))
    if not all(_finite_point(point) for point in required_points):
        return _result(face, GazeFeatureStatus.INVALID_GEOMETRY, processed_timestamp)

    left = _eye_feature(
        face,
        face.left_iris_center,
        horizontal_indices=LEFT_EYE_CORNERS,
        vertical_indices=LEFT_EYE_VERTICAL,
    )
    right = _eye_feature(
        face,
        face.right_iris_center,
        horizontal_indices=RIGHT_EYE_CORNERS,
        vertical_indices=RIGHT_EYE_VERTICAL,
    )
    if left is None or right is None:
        return _result(face, GazeFeatureStatus.INVALID_GEOMETRY, processed_timestamp)
    combined = GazeFeatureVector(
        horizontal=(left.horizontal + right.horizontal) / 2.0,
        vertical=(left.vertical + right.vertical) / 2.0,
    )
    if not _finite_feature(combined):
        return _result(face, GazeFeatureStatus.INVALID_GEOMETRY, processed_timestamp)
    return GazeFeatureObservation(
        source_sequence=face.source_sequence,
        capture_timestamp=face.capture_timestamp,
        processed_timestamp=processed_timestamp,
        status=GazeFeatureStatus.READY,
        left_eye=left,
        right_eye=right,
        combined=combined,
        face_confidence=face.confidence,
    )


def _eye_feature(
    face: FaceObservation,
    iris: NormalizedPoint,
    *,
    horizontal_indices: tuple[int, int],
    vertical_indices: tuple[int, int],
) -> GazeFeatureVector | None:
    horizontal = _projected_ratio(
        face.landmarks[horizontal_indices[0]],
        face.landmarks[horizontal_indices[1]],
        iris,
        width=float(face.frame_width),
        height=float(face.frame_height),
    )
    vertical = _projected_ratio(
        face.landmarks[vertical_indices[0]],
        face.landmarks[vertical_indices[1]],
        iris,
        width=float(face.frame_width),
        height=float(face.frame_height),
    )
    if horizontal is None or vertical is None:
        return None
    feature = GazeFeatureVector(horizontal=horizontal, vertical=vertical)
    return feature if _finite_feature(feature) else None


def _projected_ratio(
    origin: NormalizedPoint,
    endpoint: NormalizedPoint,
    sample: NormalizedPoint,
    *,
    width: float,
    height: float,
) -> float | None:
    axis_x = (endpoint.x - origin.x) * width
    axis_y = (endpoint.y - origin.y) * height
    denominator = axis_x * axis_x + axis_y * axis_y
    if not math.isfinite(denominator) or denominator < MINIMUM_EYE_AXIS_PIXELS**2:
        return None
    sample_x = (sample.x - origin.x) * width
    sample_y = (sample.y - origin.y) * height
    ratio = (sample_x * axis_x + sample_y * axis_y) / denominator
    return ratio if math.isfinite(ratio) else None


def _result(
    face: FaceObservation,
    status: GazeFeatureStatus,
    processed_timestamp: float,
) -> GazeFeatureObservation:
    safe_processed = float(processed_timestamp) if _finite_number(processed_timestamp) else 0.0
    safe_capture = (
        float(face.capture_timestamp) if _finite_number(face.capture_timestamp) else safe_processed
    )
    safe_sequence = (
        face.source_sequence
        if isinstance(face.source_sequence, int)
        and not isinstance(face.source_sequence, bool)
        and face.source_sequence > 0
        else 0
    )
    safe_confidence = (
        float(face.confidence)
        if _finite_number(face.confidence) and 0.0 <= face.confidence <= 1.0
        else None
    )
    return GazeFeatureObservation(
        source_sequence=safe_sequence,
        capture_timestamp=safe_capture,
        processed_timestamp=safe_processed,
        status=status,
        face_confidence=safe_confidence,
    )


def _valid_time(face: FaceObservation, processed_timestamp: float) -> bool:
    return (
        isinstance(face.source_sequence, int)
        and not isinstance(face.source_sequence, bool)
        and face.source_sequence > 0
        and all(
            _finite_number(value)
            for value in (
                face.capture_timestamp,
                face.processed_timestamp,
                processed_timestamp,
            )
        )
        and face.processed_timestamp >= face.capture_timestamp
        and processed_timestamp >= face.capture_timestamp
    )


def _finite_point(point: object) -> bool:
    return (
        isinstance(point, NormalizedPoint) and _finite_number(point.x) and _finite_number(point.y)
    )


def _finite_feature(feature: GazeFeatureVector) -> bool:
    return math.isfinite(feature.horizontal) and math.isfinite(feature.vertical)


def _finite_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
