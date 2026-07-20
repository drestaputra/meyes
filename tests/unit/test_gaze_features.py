"""Deterministic, fail-closed gaze feature extraction tests."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest

from meyes.domain.observations import (
    FaceObservation,
    GazeFeatureStatus,
    NormalizedPoint,
)
from meyes.vision.gaze_features import extract_gaze_features

_DEFAULT_LEFT_IRIS = NormalizedPoint(0.60, 0.425)
_DEFAULT_RIGHT_IRIS = NormalizedPoint(0.40, 0.475)


def face_observation(
    *,
    detected: bool = True,
    left_iris: NormalizedPoint | None = _DEFAULT_LEFT_IRIS,
    right_iris: NormalizedPoint | None = _DEFAULT_RIGHT_IRIS,
) -> FaceObservation:
    landmarks = [NormalizedPoint(0.5, 0.5) for _ in range(478)]
    landmarks[362] = NormalizedPoint(0.55, 0.45)
    landmarks[263] = NormalizedPoint(0.75, 0.45)
    landmarks[386] = NormalizedPoint(0.65, 0.40)
    landmarks[374] = NormalizedPoint(0.65, 0.50)
    landmarks[33] = NormalizedPoint(0.25, 0.45)
    landmarks[133] = NormalizedPoint(0.45, 0.45)
    landmarks[159] = NormalizedPoint(0.35, 0.40)
    landmarks[145] = NormalizedPoint(0.35, 0.50)
    return FaceObservation(
        source_sequence=7,
        capture_timestamp=2.0,
        processed_timestamp=2.01,
        face_detected=detected,
        confidence=0.8,
        left_eye_openness=0.9,
        right_eye_openness=0.85,
        left_iris_center=left_iris,
        right_iris_center=right_iris,
        landmarks=tuple(landmarks),
        frame_width=640,
        frame_height=480,
    )


def test_binocular_features_are_eye_relative_and_combined() -> None:
    feature = extract_gaze_features(face_observation(), processed_timestamp=2.02)

    assert feature.status is GazeFeatureStatus.READY
    assert feature.ready
    assert feature.left_eye is not None
    assert feature.right_eye is not None
    assert feature.combined is not None
    assert feature.left_eye.horizontal == pytest.approx(0.25)
    assert feature.left_eye.vertical == pytest.approx(0.25)
    assert feature.right_eye.horizontal == pytest.approx(0.75)
    assert feature.right_eye.vertical == pytest.approx(0.75)
    assert feature.combined.horizontal == pytest.approx(0.5)
    assert feature.combined.vertical == pytest.approx(0.5)
    assert feature.face_confidence == pytest.approx(0.8)


def test_projection_uses_pixel_aspect_and_eye_local_axes() -> None:
    face = face_observation(left_iris=NormalizedPoint(0.5, 0.5))
    landmarks = list(face.landmarks)
    horizontal_origin = NormalizedPoint(0.475, 0.475)
    horizontal_endpoint = NormalizedPoint(0.575, 0.575)
    vertical_origin = NormalizedPoint(0.5421875, 0.425)
    vertical_endpoint = NormalizedPoint(0.4859375, 0.525)
    landmarks[362], landmarks[263] = horizontal_origin, horizontal_endpoint
    landmarks[386], landmarks[374] = vertical_origin, vertical_endpoint
    face = replace(face, landmarks=tuple(landmarks))

    feature = extract_gaze_features(face, processed_timestamp=2.02)

    assert feature.left_eye is not None
    assert feature.left_eye.horizontal == pytest.approx(0.25)
    assert feature.left_eye.vertical == pytest.approx(0.75)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (replace(face_observation(), face_detected=False), GazeFeatureStatus.FACE_NOT_DETECTED),
        (
            replace(face_observation(), face_detected=cast(Any, "yes")),
            GazeFeatureStatus.INVALID_GEOMETRY,
        ),
        (
            replace(face_observation(), left_eye_openness=None),
            GazeFeatureStatus.EYE_OPENNESS_UNAVAILABLE,
        ),
        (replace(face_observation(), right_eye_openness=0.2), GazeFeatureStatus.EYES_CLOSED),
        (
            replace(face_observation(), left_iris_center=None),
            GazeFeatureStatus.LANDMARKS_UNAVAILABLE,
        ),
        (
            replace(face_observation(), landmarks=()),
            GazeFeatureStatus.LANDMARKS_UNAVAILABLE,
        ),
        (
            replace(face_observation(), landmarks=cast(Any, None)),
            GazeFeatureStatus.LANDMARKS_UNAVAILABLE,
        ),
        (replace(face_observation(), frame_width=0), GazeFeatureStatus.INVALID_GEOMETRY),
        (
            replace(face_observation(), left_eye_openness=float("nan")),
            GazeFeatureStatus.INVALID_GEOMETRY,
        ),
        (
            replace(face_observation(), confidence=cast(Any, "high")),
            GazeFeatureStatus.INVALID_GEOMETRY,
        ),
        (
            replace(face_observation(), frame_width=cast(Any, True)),
            GazeFeatureStatus.INVALID_GEOMETRY,
        ),
        (
            replace(face_observation(), left_iris_center=cast(Any, "iris")),
            GazeFeatureStatus.LANDMARKS_UNAVAILABLE,
        ),
        (
            replace(face_observation(), right_eye_openness=cast(Any, "open")),
            GazeFeatureStatus.INVALID_GEOMETRY,
        ),
        (
            replace(face_observation(), capture_timestamp=float("nan")),
            GazeFeatureStatus.INVALID_TIME,
        ),
        (replace(face_observation(), source_sequence=0), GazeFeatureStatus.INVALID_TIME),
        (
            replace(face_observation(), capture_timestamp=cast(Any, "now")),
            GazeFeatureStatus.INVALID_TIME,
        ),
    ],
)
def test_unusable_observations_return_explicit_status_without_features(
    candidate: FaceObservation,
    expected: GazeFeatureStatus,
) -> None:
    feature = extract_gaze_features(candidate, processed_timestamp=2.02)

    assert feature.status is expected
    assert not feature.ready
    assert feature.left_eye is None
    assert feature.right_eye is None
    assert feature.combined is None


def test_degenerate_or_nonfinite_eye_axis_is_rejected() -> None:
    face = face_observation()
    landmarks = list(face.landmarks)
    landmarks[263] = landmarks[362]
    degenerate = replace(face, landmarks=tuple(landmarks))
    landmarks = list(face.landmarks)
    landmarks[159] = NormalizedPoint(float("inf"), 0.4)
    nonfinite = replace(face, landmarks=tuple(landmarks))

    assert (
        extract_gaze_features(degenerate, processed_timestamp=2.02).status
        is GazeFeatureStatus.INVALID_GEOMETRY
    )
    assert (
        extract_gaze_features(nonfinite, processed_timestamp=2.02).status
        is GazeFeatureStatus.INVALID_GEOMETRY
    )


def test_eye_relative_ratio_is_not_clamped_before_calibration_outlier_handling() -> None:
    face = face_observation(left_iris=NormalizedPoint(0.85, 0.425))

    feature = extract_gaze_features(face, processed_timestamp=2.02)

    assert feature.left_eye is not None
    assert feature.left_eye.horizontal == pytest.approx(1.5)


def test_runtime_arguments_are_validated() -> None:
    with pytest.raises(TypeError, match="Expected FaceObservation"):
        extract_gaze_features(object(), processed_timestamp=2.02)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"within 0\.\.1"):
        extract_gaze_features(
            face_observation(),
            processed_timestamp=2.02,
            minimum_eye_openness=float("nan"),
        )
    with pytest.raises(ValueError, match=r"within 0\.\.1"):
        extract_gaze_features(
            face_observation(),
            processed_timestamp=2.02,
            minimum_eye_openness=1.1,
        )


def test_invalid_runtime_metadata_is_sanitized_in_status_result() -> None:
    face = replace(
        face_observation(),
        source_sequence=cast(Any, True),
        capture_timestamp=cast(Any, "now"),
        confidence=cast(Any, "high"),
    )

    feature = extract_gaze_features(face, processed_timestamp=cast(Any, "later"))

    assert feature.status is GazeFeatureStatus.INVALID_TIME
    assert feature.source_sequence == 0
    assert feature.capture_timestamp == 0.0
    assert feature.processed_timestamp == 0.0
    assert feature.face_confidence is None
