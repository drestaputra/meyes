"""MediaPipe Hand Landmarker adapter and orientation normalization."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Protocol, cast

import cv2
import mediapipe as mp

from meyes.camera.models import FramePacket
from meyes.domain.observations import DetectedHand, HandObservation, HandSide, NormalizedPoint
from meyes.vision.model_paths import hand_landmarker_model_path

MonotonicClock = Callable[[], float]


class LandmarkLike(Protocol):
    x: float | None
    y: float | None
    z: float | None


class CategoryLike(Protocol):
    category_name: str | None
    score: float | None


class HandLandmarkerResultLike(Protocol):
    @property
    def handedness(self) -> Sequence[Sequence[CategoryLike]]: ...

    @property
    def hand_landmarks(self) -> Sequence[Sequence[LandmarkLike]]: ...


class HandLandmarkerEngine(Protocol):
    def detect_for_video(self, image: object, timestamp_ms: int) -> object: ...

    def close(self) -> None: ...


class MediaPipeHandLandmarker:
    """Synchronous VIDEO-mode adapter for a lower-cadence worker thread.

    MediaPipe handedness assumes selfie-mirrored input. Meyes camera frames are
    unmirrored by default, so this adapter owns both label correction and the
    optional coordinate conversion into canonical unmirrored space.
    """

    def __init__(
        self,
        *,
        model_path: str | None = None,
        source_mirrored: bool = False,
        num_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        clock: MonotonicClock = time.monotonic,
    ) -> None:
        resolved_model = model_path or str(hand_landmarker_model_path())
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=resolved_model),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._engine = cast(
            HandLandmarkerEngine,
            mp.tasks.vision.HandLandmarker.create_from_options(options),
        )
        self._source_mirrored = source_mirrored
        self._clock = clock
        self._last_timestamp_ms = -1

    def process(self, packet: FramePacket) -> HandObservation:
        """Run inference and normalize MediaPipe-specific containers."""
        rgb = cv2.cvtColor(packet.frame, cv2.COLOR_BGR2RGB)
        media_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = max(int(packet.capture_timestamp * 1000), self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        raw_result = self._engine.detect_for_video(media_image, timestamp_ms)
        return observation_from_result(
            cast(HandLandmarkerResultLike, raw_result),
            packet,
            processed_timestamp=self._clock(),
            source_mirrored=self._source_mirrored,
        )

    def close(self) -> None:
        """Release the native MediaPipe task."""
        self._engine.close()


def observation_from_result(
    result: HandLandmarkerResultLike,
    packet: FramePacket,
    *,
    processed_timestamp: float,
    source_mirrored: bool,
) -> HandObservation:
    """Convert a MediaPipe-like result into canonical hand observations."""
    hands: list[DetectedHand] = []
    for index, source_landmarks in enumerate(result.hand_landmarks):
        categories = result.handedness[index] if index < len(result.handedness) else ()
        side, confidence = _canonical_handedness(categories, source_mirrored=source_mirrored)
        landmarks = tuple(
            NormalizedPoint(
                x=_canonical_x(float(landmark.x or 0.0), source_mirrored=source_mirrored),
                y=float(landmark.y or 0.0),
                z=float(landmark.z or 0.0),
            )
            for landmark in source_landmarks
        )
        hands.append(DetectedHand(side=side, confidence=confidence, landmarks=landmarks))
    return HandObservation(
        source_sequence=packet.sequence,
        capture_timestamp=packet.capture_timestamp,
        processed_timestamp=processed_timestamp,
        hands=tuple(hands),
    )


def _canonical_handedness(
    categories: Sequence[CategoryLike], *, source_mirrored: bool
) -> tuple[HandSide, float | None]:
    valid = [
        category
        for category in categories
        if category.category_name is not None and category.score is not None
    ]
    if not valid:
        return HandSide.UNKNOWN, None
    category = max(valid, key=lambda item: float(item.score or 0.0))
    label = (category.category_name or "").casefold()
    side = {"left": HandSide.LEFT, "right": HandSide.RIGHT}.get(label, HandSide.UNKNOWN)
    if not source_mirrored:
        side = _opposite(side)
    return side, float(category.score or 0.0)


def _opposite(side: HandSide) -> HandSide:
    if side is HandSide.LEFT:
        return HandSide.RIGHT
    if side is HandSide.RIGHT:
        return HandSide.LEFT
    return HandSide.UNKNOWN


def _canonical_x(x: float, *, source_mirrored: bool) -> float:
    return 1.0 - x if source_mirrored else x
