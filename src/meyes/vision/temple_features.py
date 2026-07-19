"""Fresh face/hand pairing and aspect-correct anatomical temple features."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence

from meyes.domain.observations import (
    DetectedHand,
    FaceObservation,
    HandObservation,
    HandSide,
    NormalizedPoint,
    TempleFeatureObservation,
    TempleFeatureStatus,
    TempleProximity,
)

INDEX_FINGER_TIP = 8
RIGHT_TEMPLE_INDICES = (127, 162)
LEFT_TEMPLE_INDICES = (356, 389)
FACE_WIDTH_INDICES = (234, 454)
MINIMUM_FACE_WIDTH_PIXELS = 1.0

MonotonicClock = Callable[[], float]


class TempleFeatureTracker:
    """Pair lower-cadence hands with a bounded history of fresh face frames."""

    def __init__(
        self,
        *,
        max_pair_skew: float = 0.12,
        max_age: float = 0.25,
        face_history_size: int = 12,
        clock: MonotonicClock = time.monotonic,
    ) -> None:
        if not math.isfinite(max_pair_skew) or max_pair_skew < 0:
            raise ValueError("Maximum pair skew must be finite and non-negative")
        if not math.isfinite(max_age) or max_age <= 0:
            raise ValueError("Maximum observation age must be finite and positive")
        if face_history_size <= 0:
            raise ValueError("Face history size must be positive")
        self._max_pair_skew = max_pair_skew
        self._max_age = max_age
        self._clock = clock
        self._faces: deque[FaceObservation] = deque(maxlen=face_history_size)
        self._last_face_sequence = 0
        self._last_face_capture_timestamp: float | None = None
        self._last_hand_sequence = 0
        self._last_hand_capture_timestamp: float | None = None
        self._latest_hand: HandObservation | None = None
        self._latest: TempleFeatureObservation | None = None
        self._lock = threading.Lock()

    @property
    def latest(self) -> TempleFeatureObservation | None:
        """Return the latest immutable feature state."""
        with self._lock:
            return self._latest

    def update_face(self, observation: FaceObservation) -> bool:
        """Record a newer face observation for subsequent hand pairing."""
        with self._lock:
            if (
                observation.source_sequence <= self._last_face_sequence
                or not math.isfinite(observation.capture_timestamp)
                or (
                    self._last_face_capture_timestamp is not None
                    and observation.capture_timestamp <= self._last_face_capture_timestamp
                )
            ):
                return False
            self._last_face_sequence = observation.source_sequence
            self._last_face_capture_timestamp = observation.capture_timestamp
            self._faces.append(observation)
            return True

    def update_hand(self, observation: HandObservation) -> TempleFeatureObservation:
        """Pair one newer hand frame and extract same-side temple distances."""
        with self._lock:
            now = self._clock()
            if not math.isfinite(now):
                raise RuntimeError("Monotonic clock returned a non-finite value")
            if observation.source_sequence <= self._last_hand_sequence:
                return _status_observation(
                    observation,
                    TempleFeatureStatus.OUT_OF_ORDER,
                    processed_timestamp=now,
                )
            self._last_hand_sequence = observation.source_sequence
            if not math.isfinite(observation.capture_timestamp):
                return self._store(
                    _status_observation(
                        observation,
                        TempleFeatureStatus.INVALID_TIME,
                        processed_timestamp=now,
                    )
                )
            if (
                self._last_hand_capture_timestamp is not None
                and observation.capture_timestamp <= self._last_hand_capture_timestamp
            ):
                return _status_observation(
                    observation,
                    TempleFeatureStatus.OUT_OF_ORDER,
                    processed_timestamp=now,
                )
            self._last_hand_capture_timestamp = observation.capture_timestamp
            hand_age = now - observation.capture_timestamp
            if hand_age < 0 or hand_age > self._max_age:
                self._latest_hand = None
                return self._store(
                    _status_observation(
                        observation,
                        TempleFeatureStatus.HAND_STALE,
                        processed_timestamp=now,
                    )
                )
            self._latest_hand = observation
            return self._store(self._pair_hand(observation, now))

    def recompute_latest_hand(self) -> TempleFeatureObservation | None:
        """Re-pair one cached hand when its matching face arrives later."""
        with self._lock:
            hands = self._latest_hand
            latest = self._latest
            if (
                hands is None
                or latest is None
                or latest.source_sequence != hands.source_sequence
                or latest.status
                not in {
                    TempleFeatureStatus.FACE_UNAVAILABLE,
                    TempleFeatureStatus.PAIR_SKEW,
                    TempleFeatureStatus.FACE_NOT_DETECTED,
                    TempleFeatureStatus.INVALID_GEOMETRY,
                }
            ):
                return None
            now = self._clock()
            if not math.isfinite(now):
                raise RuntimeError("Monotonic clock returned a non-finite value")
            if now - hands.capture_timestamp > self._max_age:
                self._latest_hand = None
                return self._store(
                    _status_observation(
                        hands,
                        TempleFeatureStatus.HAND_STALE,
                        processed_timestamp=now,
                    )
                )
            refreshed = self._pair_hand(hands, now)
            if refreshed == latest:
                return None
            return self._store(refreshed)

    def expire(self) -> TempleFeatureObservation | None:
        """Expire a previously valid pair even when no new observations arrive."""
        with self._lock:
            latest = self._latest
            if latest is None or not latest.valid_pair:
                return None
            now = self._clock()
            if not math.isfinite(now):
                raise RuntimeError("Monotonic clock returned a non-finite value")
            oldest_input_timestamp = min(
                latest.capture_timestamp,
                latest.face_capture_timestamp
                if latest.face_capture_timestamp is not None
                else latest.capture_timestamp,
            )
            if now - oldest_input_timestamp <= self._max_age:
                return None
            expired = TempleFeatureObservation(
                source_sequence=latest.source_sequence,
                capture_timestamp=now,
                processed_timestamp=now,
                status=TempleFeatureStatus.EXPIRED,
                face_source_sequence=latest.face_source_sequence,
                face_capture_timestamp=latest.face_capture_timestamp,
                pair_skew_ms=latest.pair_skew_ms,
            )
            return self._store(expired)

    def reset(self) -> None:
        """Drop all history and feature state after tracking suspension."""
        with self._lock:
            self._faces.clear()
            self._last_face_sequence = 0
            self._last_face_capture_timestamp = None
            self._last_hand_sequence = 0
            self._last_hand_capture_timestamp = None
            self._latest_hand = None
            self._latest = None

    def _store(self, observation: TempleFeatureObservation) -> TempleFeatureObservation:
        self._latest = observation
        return observation

    def _pair_hand(self, observation: HandObservation, now: float) -> TempleFeatureObservation:
        faces = [
            face
            for face in self._faces
            if math.isfinite(face.capture_timestamp)
            and 0 <= now - face.capture_timestamp <= self._max_age
        ]
        if not faces:
            return _status_observation(
                observation,
                TempleFeatureStatus.FACE_UNAVAILABLE,
                processed_timestamp=now,
            )
        face = _best_face_match(faces, observation)
        pair_skew = abs(face.capture_timestamp - observation.capture_timestamp)
        if not math.isfinite(pair_skew):
            return _status_observation(
                observation,
                TempleFeatureStatus.INVALID_TIME,
                processed_timestamp=now,
                face=face,
            )
        if pair_skew > self._max_pair_skew:
            return _status_observation(
                observation,
                TempleFeatureStatus.PAIR_SKEW,
                processed_timestamp=now,
                face=face,
                pair_skew=pair_skew,
            )
        return extract_temple_features(
            face,
            observation,
            processed_timestamp=now,
        )


def extract_temple_features(
    face: FaceObservation,
    hands: HandObservation,
    *,
    processed_timestamp: float,
) -> TempleFeatureObservation:
    """Calculate same-side fingertip distance normalized by pixel-space face width."""
    if not all(
        math.isfinite(value)
        for value in (
            face.capture_timestamp,
            hands.capture_timestamp,
            processed_timestamp,
        )
    ):
        return TempleFeatureObservation(
            source_sequence=hands.source_sequence,
            capture_timestamp=hands.capture_timestamp,
            processed_timestamp=processed_timestamp,
            status=TempleFeatureStatus.INVALID_TIME,
            face_source_sequence=face.source_sequence,
            face_capture_timestamp=face.capture_timestamp,
        )
    pair_skew = abs(face.capture_timestamp - hands.capture_timestamp)
    if not face.face_detected:
        return _paired_observation(
            face,
            hands,
            TempleFeatureStatus.FACE_NOT_DETECTED,
            processed_timestamp=processed_timestamp,
            pair_skew=pair_skew,
        )
    if not _valid_frame_geometry(face, hands):
        return _paired_observation(
            face,
            hands,
            TempleFeatureStatus.INVALID_GEOMETRY,
            processed_timestamp=processed_timestamp,
            pair_skew=pair_skew,
        )

    assert face.frame_width > 0
    assert face.frame_height > 0
    width = float(face.frame_width)
    height = float(face.frame_height)
    face_width = _pixel_distance(
        face.landmarks[FACE_WIDTH_INDICES[0]],
        face.landmarks[FACE_WIDTH_INDICES[1]],
        width,
        height,
    )
    if not math.isfinite(face_width) or face_width <= MINIMUM_FACE_WIDTH_PIXELS:
        return _paired_observation(
            face,
            hands,
            TempleFeatureStatus.INVALID_GEOMETRY,
            processed_timestamp=processed_timestamp,
            pair_skew=pair_skew,
        )

    proximities: list[TempleProximity] = []
    for side, indices in (
        (HandSide.LEFT, LEFT_TEMPLE_INDICES),
        (HandSide.RIGHT, RIGHT_TEMPLE_INDICES),
    ):
        anchor = _mean_points(face.landmarks, indices)
        if anchor is None:
            continue
        hand = _best_complete_hand(hands.hands, side, anchor, width, height)
        if hand is None:
            continue
        fingertip = hand.landmark(INDEX_FINGER_TIP)
        if fingertip is None:
            continue
        distance = _pixel_distance(fingertip, anchor, width, height)
        ratio = distance / face_width
        confidence = hand.confidence
        if not math.isfinite(ratio) or confidence is None:
            continue
        proximities.append(
            TempleProximity(
                side=side,
                distance_ratio=ratio,
                hand_confidence=confidence,
            )
        )
    status = TempleFeatureStatus.READY if proximities else TempleFeatureStatus.NO_ELIGIBLE_HANDS
    return _paired_observation(
        face,
        hands,
        status,
        processed_timestamp=processed_timestamp,
        pair_skew=pair_skew,
        proximities=tuple(proximities),
    )


def _paired_observation(
    face: FaceObservation,
    hands: HandObservation,
    status: TempleFeatureStatus,
    *,
    processed_timestamp: float,
    pair_skew: float,
    proximities: tuple[TempleProximity, ...] = (),
) -> TempleFeatureObservation:
    return TempleFeatureObservation(
        source_sequence=hands.source_sequence,
        capture_timestamp=hands.capture_timestamp,
        processed_timestamp=processed_timestamp,
        status=status,
        face_source_sequence=face.source_sequence,
        face_capture_timestamp=face.capture_timestamp,
        pair_skew_ms=pair_skew * 1000.0,
        proximities=proximities,
    )


def _status_observation(
    hands: HandObservation,
    status: TempleFeatureStatus,
    *,
    processed_timestamp: float,
    face: FaceObservation | None = None,
    pair_skew: float | None = None,
) -> TempleFeatureObservation:
    return TempleFeatureObservation(
        source_sequence=hands.source_sequence,
        capture_timestamp=hands.capture_timestamp,
        processed_timestamp=processed_timestamp,
        status=status,
        face_source_sequence=face.source_sequence if face is not None else None,
        face_capture_timestamp=face.capture_timestamp if face is not None else None,
        pair_skew_ms=pair_skew * 1000.0 if pair_skew is not None else None,
    )


def _best_face_match(faces: Sequence[FaceObservation], hands: HandObservation) -> FaceObservation:
    same_sequence = [face for face in faces if face.source_sequence == hands.source_sequence]
    if same_sequence:
        return same_sequence[-1]
    return min(faces, key=lambda face: abs(face.capture_timestamp - hands.capture_timestamp))


def _valid_frame_geometry(face: FaceObservation, hands: HandObservation) -> bool:
    if (
        face.frame_width <= 0
        or face.frame_height <= 0
        or hands.frame_width != face.frame_width
        or hands.frame_height != face.frame_height
        or len(face.landmarks)
        <= max(*FACE_WIDTH_INDICES, *LEFT_TEMPLE_INDICES, *RIGHT_TEMPLE_INDICES)
    ):
        return False
    required = [
        face.landmarks[index]
        for index in (*FACE_WIDTH_INDICES, *LEFT_TEMPLE_INDICES, *RIGHT_TEMPLE_INDICES)
    ]
    return all(_finite_point(point) for point in required)


def _best_complete_hand(
    hands: Sequence[DetectedHand],
    side: HandSide,
    anchor: NormalizedPoint,
    width: float,
    height: float,
) -> DetectedHand | None:
    candidates = [
        hand
        for hand in hands
        if hand.side is side
        and hand.confidence is not None
        and math.isfinite(hand.confidence)
        and 0.0 <= hand.confidence <= 1.0
        and (tip := hand.landmark(INDEX_FINGER_TIP)) is not None
        and _finite_point(tip)
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda hand: _hand_selection_key(hand, anchor, width, height),
    )


def _hand_selection_key(
    hand: DetectedHand,
    anchor: NormalizedPoint,
    width: float,
    height: float,
) -> tuple[float, float, float, float]:
    confidence = hand.confidence or 0.0
    fingertip = hand.landmark(INDEX_FINGER_TIP)
    assert fingertip is not None
    return (
        -confidence,
        _pixel_distance(fingertip, anchor, width, height),
        fingertip.x,
        fingertip.y,
    )


def _mean_points(
    landmarks: Sequence[NormalizedPoint], indices: Sequence[int]
) -> NormalizedPoint | None:
    if not indices or max(indices) >= len(landmarks):
        return None
    selected = [landmarks[index] for index in indices]
    if not all(_finite_point(point) for point in selected):
        return None
    return NormalizedPoint(
        x=sum(point.x for point in selected) / len(selected),
        y=sum(point.y for point in selected) / len(selected),
    )


def _pixel_distance(
    first: NormalizedPoint,
    second: NormalizedPoint,
    width: float,
    height: float,
) -> float:
    return math.hypot((first.x - second.x) * width, (first.y - second.y) * height)


def _finite_point(point: NormalizedPoint) -> bool:
    return math.isfinite(point.x) and math.isfinite(point.y)
