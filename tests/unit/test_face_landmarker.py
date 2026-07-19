"""MediaPipe result normalization tests using lightweight fakes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import pytest

from meyes.camera.models import FramePacket
from meyes.domain.observations import FaceObservation
from meyes.vision.face_landmarker import FaceLandmarkerResultLike, observation_from_result


@dataclass
class FakeLandmark:
    x: float | None
    y: float | None
    z: float | None = 0.0
    presence: float | None = None


@dataclass
class FakeCategory:
    category_name: str | None
    score: float | None


@dataclass
class FakeResult:
    face_landmarks: list[list[FakeLandmark]]
    face_blendshapes: list[list[FakeCategory]]


def frame_packet() -> FramePacket:
    return FramePacket(
        sequence=4,
        capture_timestamp=10.0,
        frame=np.zeros((2, 2, 3), dtype=np.uint8),
    )


def normalized(result: FakeResult, processed_timestamp: float = 10.02) -> FaceObservation:
    return observation_from_result(
        cast(FaceLandmarkerResultLike, result),
        frame_packet(),
        processed_timestamp=processed_timestamp,
    )


def test_no_face_produces_explicit_empty_observation() -> None:
    observation = normalized(FakeResult(face_landmarks=[], face_blendshapes=[]))

    assert observation.face_detected is False
    assert observation.left_eye_openness is None
    assert observation.right_eye_openness is None
    assert observation.landmarks == ()
    assert observation.frame_width == 2
    assert observation.frame_height == 2
    assert observation.processing_latency_ms == pytest.approx(20.0)


def test_blendshapes_become_independent_eye_openness() -> None:
    landmarks = [FakeLandmark(x=index / 1000, y=index / 2000) for index in range(478)]
    result = FakeResult(
        face_landmarks=[landmarks],
        face_blendshapes=[
            [
                FakeCategory("eyeBlinkLeft", 0.8),
                FakeCategory("eyeBlinkRight", 0.1),
            ]
        ],
    )

    observation = normalized(result, processed_timestamp=10.01)

    assert observation.face_detected is True
    assert observation.left_eye_openness == pytest.approx(0.2)
    assert observation.right_eye_openness == pytest.approx(0.9)
    assert observation.left_iris_center is not None
    assert observation.right_iris_center is not None
    assert observation.left_iris_center.x == pytest.approx(sum(range(473, 478)) / 5000)
    assert observation.right_iris_center.x == pytest.approx(sum(range(468, 473)) / 5000)
    assert len(observation.landmarks) == 478


def test_presence_confidence_is_honest_when_unavailable() -> None:
    without_presence = FakeResult(
        face_landmarks=[[FakeLandmark(0.5, 0.5)]],
        face_blendshapes=[],
    )
    with_presence = FakeResult(
        face_landmarks=[
            [FakeLandmark(0.5, 0.5, presence=0.7), FakeLandmark(0.6, 0.5, presence=0.9)]
        ],
        face_blendshapes=[],
    )

    unknown = normalized(without_presence, processed_timestamp=10.01)
    measured = normalized(with_presence, processed_timestamp=10.01)

    assert unknown.confidence is None
    assert measured.confidence == pytest.approx(0.8)
