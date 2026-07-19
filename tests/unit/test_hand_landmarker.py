"""MediaPipe hand result normalization tests using lightweight fakes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import pytest

from meyes.camera.models import FramePacket
from meyes.domain.observations import HandObservation, HandSide
from meyes.vision.hand_landmarker import HandLandmarkerResultLike, observation_from_result


@dataclass
class FakeLandmark:
    x: float | None
    y: float | None
    z: float | None = 0.0


@dataclass
class FakeCategory:
    category_name: str | None
    score: float | None


@dataclass
class FakeResult:
    handedness: list[list[FakeCategory]]
    hand_landmarks: list[list[FakeLandmark]]


def frame_packet() -> FramePacket:
    return FramePacket(
        sequence=9,
        capture_timestamp=20.0,
        frame=np.zeros((2, 2, 3), dtype=np.uint8),
    )


def normalized(result: FakeResult, *, source_mirrored: bool) -> HandObservation:
    return observation_from_result(
        cast(HandLandmarkerResultLike, result),
        frame_packet(),
        processed_timestamp=20.025,
        source_mirrored=source_mirrored,
    )


def test_no_hands_produces_explicit_empty_observation() -> None:
    observation = normalized(
        FakeResult(handedness=[], hand_landmarks=[]),
        source_mirrored=False,
    )

    assert observation.hand_detected is False
    assert observation.hands == ()
    assert observation.processing_latency_ms == pytest.approx(25.0)


def test_unmirrored_input_swaps_model_handedness_only() -> None:
    observation = normalized(
        FakeResult(
            handedness=[[FakeCategory("Left", 0.92)]],
            hand_landmarks=[[FakeLandmark(0.2, 0.4), FakeLandmark(0.3, 0.5)]],
        ),
        source_mirrored=False,
    )

    hand = observation.hand(HandSide.RIGHT)

    assert hand is not None
    assert hand.confidence == pytest.approx(0.92)
    assert hand.landmarks[0].x == pytest.approx(0.2)
    assert observation.hand(HandSide.LEFT) is None


def test_mirrored_input_keeps_model_handedness_and_unmirrors_coordinates() -> None:
    observation = normalized(
        FakeResult(
            handedness=[[FakeCategory("Left", 0.88)]],
            hand_landmarks=[[FakeLandmark(0.2, 0.4)]],
        ),
        source_mirrored=True,
    )

    hand = observation.hand(HandSide.LEFT)

    assert hand is not None
    assert hand.landmarks[0].x == pytest.approx(0.8)
    assert hand.landmarks[0].y == pytest.approx(0.4)


def test_missing_or_unknown_handedness_remains_explicit() -> None:
    observation = normalized(
        FakeResult(
            handedness=[[FakeCategory("ambiguous", 0.4)]],
            hand_landmarks=[[FakeLandmark(0.5, 0.5)]],
        ),
        source_mirrored=False,
    )

    assert observation.hands[0].side is HandSide.UNKNOWN
    assert observation.hands[0].confidence == pytest.approx(0.4)
    assert observation.hands[0].landmark(21) is None
