"""MediaPipe Face Landmarker adapter and result normalization."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Protocol, cast

import cv2
import mediapipe as mp
import numpy as np

from meyes.camera.models import FramePacket
from meyes.domain.observations import FaceObservation, NormalizedPoint
from meyes.vision.model_paths import face_landmarker_model_path

LEFT_IRIS_INDICES = (473, 474, 475, 476, 477)
RIGHT_IRIS_INDICES = (468, 469, 470, 471, 472)
LEFT_BLINK_NAME = "eyeBlinkLeft"
RIGHT_BLINK_NAME = "eyeBlinkRight"

MonotonicClock = Callable[[], float]


class LandmarkLike(Protocol):
    x: float | None
    y: float | None
    z: float | None
    presence: float | None


class CategoryLike(Protocol):
    category_name: str | None
    score: float | None


class FaceLandmarkerResultLike(Protocol):
    @property
    def face_landmarks(self) -> Sequence[Sequence[LandmarkLike]]: ...

    @property
    def face_blendshapes(self) -> Sequence[Sequence[CategoryLike]]: ...


class FaceLandmarkerEngine(Protocol):
    def detect_for_video(self, image: object, timestamp_ms: int) -> object: ...

    def close(self) -> None: ...


class MediaPipeFaceLandmarker:
    """Synchronous VIDEO-mode adapter intended for a dedicated worker thread."""

    def __init__(
        self,
        *,
        model_path: str | None = None,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        clock: MonotonicClock = time.monotonic,
    ) -> None:
        resolved_model = model_path or str(face_landmarker_model_path())
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=resolved_model),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=False,
        )
        self._engine = cast(
            FaceLandmarkerEngine,
            mp.tasks.vision.FaceLandmarker.create_from_options(options),
        )
        self._clock = clock
        self._last_timestamp_ms = -1

    def process(self, packet: FramePacket) -> FaceObservation:
        """Run inference and normalize MediaPipe-specific containers."""
        rgb = cv2.cvtColor(packet.frame, cv2.COLOR_BGR2RGB)
        media_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = max(int(packet.capture_timestamp * 1000), self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        raw_result = self._engine.detect_for_video(media_image, timestamp_ms)
        result = cast(FaceLandmarkerResultLike, raw_result)
        return observation_from_result(result, packet, processed_timestamp=self._clock())

    def close(self) -> None:
        """Release the native MediaPipe task."""
        self._engine.close()


def observation_from_result(
    result: FaceLandmarkerResultLike,
    packet: FramePacket,
    *,
    processed_timestamp: float,
) -> FaceObservation:
    """Convert a MediaPipe-like result into a framework-independent observation."""
    if not result.face_landmarks:
        return FaceObservation(
            source_sequence=packet.sequence,
            capture_timestamp=packet.capture_timestamp,
            processed_timestamp=processed_timestamp,
            face_detected=False,
        )

    source_landmarks = result.face_landmarks[0]
    landmarks = tuple(
        NormalizedPoint(
            x=float(landmark.x or 0.0),
            y=float(landmark.y or 0.0),
            z=float(landmark.z or 0.0),
        )
        for landmark in source_landmarks
    )
    blendshapes = _blendshape_scores(result)
    return FaceObservation(
        source_sequence=packet.sequence,
        capture_timestamp=packet.capture_timestamp,
        processed_timestamp=processed_timestamp,
        face_detected=True,
        confidence=_mean_landmark_presence(source_landmarks),
        left_eye_openness=_openness(blendshapes.get(LEFT_BLINK_NAME)),
        right_eye_openness=_openness(blendshapes.get(RIGHT_BLINK_NAME)),
        left_iris_center=_mean_point(landmarks, LEFT_IRIS_INDICES),
        right_iris_center=_mean_point(landmarks, RIGHT_IRIS_INDICES),
        landmarks=landmarks,
    )


def _blendshape_scores(result: FaceLandmarkerResultLike) -> dict[str, float]:
    if not result.face_blendshapes:
        return {}
    scores: dict[str, float] = {}
    for category in result.face_blendshapes[0]:
        if category.category_name is not None and category.score is not None:
            scores[category.category_name] = float(category.score)
    return scores


def _openness(blink_score: float | None) -> float | None:
    if blink_score is None:
        return None
    return float(np.clip(1.0 - blink_score, 0.0, 1.0))


def _mean_landmark_presence(landmarks: Sequence[LandmarkLike]) -> float | None:
    presence = [float(item.presence) for item in landmarks if item.presence is not None]
    if not presence:
        return None
    return float(np.clip(np.mean(presence), 0.0, 1.0))


def _mean_point(
    landmarks: Sequence[NormalizedPoint], indices: Sequence[int]
) -> NormalizedPoint | None:
    if not indices or max(indices) >= len(landmarks):
        return None
    selected = [landmarks[index] for index in indices]
    return NormalizedPoint(
        x=sum(point.x for point in selected) / len(selected),
        y=sum(point.y for point in selected) / len(selected),
        z=sum(point.z for point in selected) / len(selected),
    )
