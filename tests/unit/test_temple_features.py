"""Deterministic face/hand pairing and temple geometry tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from meyes.domain.observations import (
    DetectedHand,
    FaceObservation,
    HandObservation,
    HandSide,
    NormalizedPoint,
    TempleFeatureStatus,
)
from meyes.vision.temple_features import TempleFeatureTracker, extract_temple_features


class FakeClock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def face_observation(
    *,
    sequence: int = 10,
    captured: float = 10.0,
    processed: float | None = None,
    detected: bool = True,
) -> FaceObservation:
    landmarks = [NormalizedPoint(0.5, 0.5) for _ in range(478)]
    for index in (127, 162):
        landmarks[index] = NormalizedPoint(0.2, 0.4)
    for index in (356, 389):
        landmarks[index] = NormalizedPoint(0.8, 0.4)
    for index in (50, 101, 205):
        landmarks[index] = NormalizedPoint(0.35, 0.55)
    for index in (280, 330, 425):
        landmarks[index] = NormalizedPoint(0.65, 0.55)
    landmarks[234] = NormalizedPoint(0.2, 0.4)
    landmarks[454] = NormalizedPoint(0.8, 0.4)
    return FaceObservation(
        source_sequence=sequence,
        capture_timestamp=captured,
        processed_timestamp=processed if processed is not None else captured + 0.01,
        face_detected=detected,
        landmarks=tuple(landmarks),
        frame_width=640,
        frame_height=480,
    )


def detected_hand(
    side: HandSide,
    tip: tuple[float, float],
    *,
    confidence: float = 0.9,
) -> DetectedHand:
    landmarks = [NormalizedPoint(0.5, 0.5) for _ in range(21)]
    landmarks[8] = NormalizedPoint(*tip)
    return DetectedHand(side=side, confidence=confidence, landmarks=tuple(landmarks))


def hand_observation(
    *hands: DetectedHand,
    sequence: int = 10,
    captured: float = 10.0,
    processed: float | None = None,
) -> HandObservation:
    return HandObservation(
        source_sequence=sequence,
        capture_timestamp=captured,
        processed_timestamp=processed if processed is not None else captured + 0.02,
        hands=hands,
        frame_width=640,
        frame_height=480,
    )


def test_pixel_geometry_corrects_horizontal_and_vertical_aspect_ratio() -> None:
    face = face_observation()
    horizontal = extract_temple_features(
        face,
        hand_observation(detected_hand(HandSide.RIGHT, (0.26, 0.4))),
        processed_timestamp=10.03,
    )
    vertical = extract_temple_features(
        face,
        hand_observation(detected_hand(HandSide.RIGHT, (0.2, 0.48))),
        processed_timestamp=10.03,
    )

    assert horizontal.status is TempleFeatureStatus.READY
    horizontal_right = horizontal.proximity(HandSide.RIGHT)
    vertical_right = vertical.proximity(HandSide.RIGHT)
    assert horizontal_right is not None
    assert vertical_right is not None
    assert horizontal_right.distance_ratio == pytest.approx(0.1)
    assert vertical_right.distance_ratio == pytest.approx(0.1)


def test_anatomical_hand_is_never_reassigned_to_the_closest_temple() -> None:
    result = extract_temple_features(
        face_observation(),
        hand_observation(detected_hand(HandSide.LEFT, (0.2, 0.4))),
        processed_timestamp=10.03,
    )

    left = result.proximity(HandSide.LEFT)
    assert left is not None
    assert left.distance_ratio == pytest.approx(1.0)
    assert result.proximity(HandSide.RIGHT) is None


def test_cheek_anchors_are_distinct_and_anatomically_sided() -> None:
    result = extract_temple_features(
        face_observation(),
        hand_observation(
            detected_hand(HandSide.RIGHT, (0.35, 0.55)),
            detected_hand(HandSide.LEFT, (0.65, 0.55)),
        ),
        processed_timestamp=10.03,
    )

    left = result.cheek_proximity(HandSide.LEFT)
    right = result.cheek_proximity(HandSide.RIGHT)
    assert left is not None and left.distance_ratio == pytest.approx(0.0)
    assert right is not None and right.distance_ratio == pytest.approx(0.0)
    assert result.proximity(HandSide.LEFT) is not None
    assert result.proximity(HandSide.RIGHT) is not None


def test_unknown_hand_is_ignored_and_duplicate_side_uses_highest_confidence() -> None:
    result = extract_temple_features(
        face_observation(),
        hand_observation(
            detected_hand(HandSide.UNKNOWN, (0.2, 0.4), confidence=0.99),
            detected_hand(HandSide.RIGHT, (0.8, 0.4), confidence=0.7),
            detected_hand(HandSide.RIGHT, (0.26, 0.4), confidence=0.95),
        ),
        processed_timestamp=10.03,
    )

    right = result.proximity(HandSide.RIGHT)
    assert right is not None
    assert right.distance_ratio == pytest.approx(0.1)
    assert right.hand_confidence == pytest.approx(0.95)
    assert len(result.proximities) == 1


def test_equal_confidence_duplicate_is_order_independent_and_uses_closest_tip() -> None:
    near = detected_hand(HandSide.RIGHT, (0.26, 0.4), confidence=0.9)
    far = detected_hand(HandSide.RIGHT, (0.8, 0.4), confidence=0.9)

    forward = extract_temple_features(
        face_observation(),
        hand_observation(far, near),
        processed_timestamp=10.03,
    )
    reversed_order = extract_temple_features(
        face_observation(),
        hand_observation(near, far),
        processed_timestamp=10.03,
    )

    forward_right = forward.proximity(HandSide.RIGHT)
    reversed_right = reversed_order.proximity(HandSide.RIGHT)
    assert forward_right is not None
    assert reversed_right is not None
    assert forward_right.distance_ratio == pytest.approx(0.1)
    assert reversed_right.distance_ratio == pytest.approx(0.1)


def test_both_anatomical_sides_have_stable_output_order() -> None:
    result = extract_temple_features(
        face_observation(),
        hand_observation(
            detected_hand(HandSide.RIGHT, (0.2, 0.4)),
            detected_hand(HandSide.LEFT, (0.8, 0.4)),
        ),
        processed_timestamp=10.03,
    )

    assert [item.side for item in result.proximities] == [HandSide.LEFT, HandSide.RIGHT]
    assert [item.side for item in result.cheek_proximities] == [
        HandSide.LEFT,
        HandSide.RIGHT,
    ]


@pytest.mark.parametrize(
    ("face", "hands", "status"),
    [
        (
            face_observation(detected=False),
            hand_observation(detected_hand(HandSide.RIGHT, (0.2, 0.4))),
            TempleFeatureStatus.FACE_NOT_DETECTED,
        ),
        (
            replace(face_observation(), landmarks=(NormalizedPoint(0.5, 0.5),)),
            hand_observation(detected_hand(HandSide.RIGHT, (0.2, 0.4))),
            TempleFeatureStatus.INVALID_GEOMETRY,
        ),
        (
            face_observation(),
            replace(
                hand_observation(detected_hand(HandSide.RIGHT, (0.2, 0.4))),
                frame_width=800,
            ),
            TempleFeatureStatus.INVALID_GEOMETRY,
        ),
    ],
)
def test_invalid_face_or_frame_geometry_is_explicit(
    face: FaceObservation,
    hands: HandObservation,
    status: TempleFeatureStatus,
) -> None:
    result = extract_temple_features(face, hands, processed_timestamp=10.03)

    assert result.status is status
    assert result.proximities == ()


def test_zero_face_width_and_nonfinite_tip_never_emit_a_distance() -> None:
    zero_width_face = face_observation()
    landmarks = list(zero_width_face.landmarks)
    landmarks[454] = landmarks[234]
    zero_width_face = replace(zero_width_face, landmarks=tuple(landmarks))
    zero_width = extract_temple_features(
        zero_width_face,
        hand_observation(detected_hand(HandSide.RIGHT, (0.2, 0.4))),
        processed_timestamp=10.03,
    )
    nonfinite_tip = extract_temple_features(
        face_observation(),
        hand_observation(detected_hand(HandSide.RIGHT, (float("nan"), 0.4))),
        processed_timestamp=10.03,
    )

    assert zero_width.status is TempleFeatureStatus.INVALID_GEOMETRY
    assert nonfinite_tip.status is TempleFeatureStatus.NO_ELIGIBLE_HANDS


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_handedness_confidence_is_not_eligible(confidence: float) -> None:
    result = extract_temple_features(
        face_observation(),
        hand_observation(detected_hand(HandSide.RIGHT, (0.2, 0.4), confidence=confidence)),
        processed_timestamp=10.03,
    )

    assert result.status is TempleFeatureStatus.NO_ELIGIBLE_HANDS


def test_subpixel_face_width_is_rejected_as_collapsed_geometry() -> None:
    face = face_observation()
    landmarks = list(face.landmarks)
    landmarks[234] = NormalizedPoint(0.5, 0.4)
    landmarks[454] = NormalizedPoint(0.5005, 0.4)
    collapsed = replace(face, landmarks=tuple(landmarks))

    result = extract_temple_features(
        collapsed,
        hand_observation(detected_hand(HandSide.RIGHT, (0.2, 0.4))),
        processed_timestamp=10.03,
    )

    assert result.status is TempleFeatureStatus.INVALID_GEOMETRY


def test_empty_or_incomplete_hands_form_a_valid_pair_without_features() -> None:
    incomplete = DetectedHand(
        side=HandSide.RIGHT,
        confidence=0.9,
        landmarks=(NormalizedPoint(0.2, 0.4),),
    )
    result = extract_temple_features(
        face_observation(),
        hand_observation(incomplete),
        processed_timestamp=10.03,
    )

    assert result.status is TempleFeatureStatus.NO_ELIGIBLE_HANDS
    assert result.valid_pair


def test_tracker_prefers_same_sequence_then_enforces_pair_skew() -> None:
    clock = FakeClock(10.1)
    tracker = TempleFeatureTracker(max_pair_skew=0.12, clock=clock)
    tracker.update_face(face_observation(sequence=8, captured=9.90))
    tracker.update_face(face_observation(sequence=9, captured=9.99))

    result = tracker.update_hand(
        hand_observation(
            detected_hand(HandSide.RIGHT, (0.2, 0.4)),
            sequence=8,
            captured=10.0,
        )
    )

    assert result.status is TempleFeatureStatus.READY
    assert result.face_source_sequence == 8
    assert result.pair_skew_ms == pytest.approx(100.0)

    skew_tracker = TempleFeatureTracker(max_pair_skew=0.12, clock=clock)
    skew_tracker.update_face(face_observation(sequence=10, captured=10.20))
    clock.now = 10.21
    skewed = skew_tracker.update_hand(
        hand_observation(
            detected_hand(HandSide.RIGHT, (0.2, 0.4)),
            sequence=11,
            captured=10.0,
        )
    )
    assert skewed.status is TempleFeatureStatus.PAIR_SKEW


def test_tracker_chooses_nearest_capture_time_when_no_sequence_matches() -> None:
    clock = FakeClock(10.05)
    tracker = TempleFeatureTracker(clock=clock)
    tracker.update_face(face_observation(sequence=1, captured=9.8))
    tracker.update_face(face_observation(sequence=2, captured=9.95))

    result = tracker.update_hand(hand_observation(sequence=3, captured=10.0))

    assert result.valid_pair
    assert result.face_source_sequence == 2


def test_tracker_recomputes_cached_hand_when_same_frame_face_arrives_later() -> None:
    clock = FakeClock(10.0)
    tracker = TempleFeatureTracker(clock=clock)
    unavailable = tracker.update_hand(
        hand_observation(
            detected_hand(HandSide.RIGHT, (0.2, 0.4)),
            sequence=1,
            captured=9.95,
        )
    )

    assert unavailable.status is TempleFeatureStatus.FACE_UNAVAILABLE
    assert tracker.update_face(face_observation(sequence=1, captured=9.95))
    refreshed = tracker.recompute_latest_hand()

    assert refreshed is not None
    assert refreshed.status is TempleFeatureStatus.READY
    assert refreshed.face_source_sequence == 1
    assert tracker.recompute_latest_hand() is None


def test_tracker_accepts_pair_skew_boundary_and_rejects_beyond_it() -> None:
    clock = FakeClock(10.1)
    boundary = TempleFeatureTracker(max_pair_skew=0.12, clock=clock)
    boundary.update_face(face_observation(sequence=1, captured=9.88))
    accepted = boundary.update_hand(hand_observation(sequence=2, captured=10.0))

    beyond = TempleFeatureTracker(max_pair_skew=0.12, clock=clock)
    beyond.update_face(face_observation(sequence=1, captured=9.879))
    rejected = beyond.update_hand(hand_observation(sequence=2, captured=10.0))

    assert accepted.valid_pair
    assert rejected.status is TempleFeatureStatus.PAIR_SKEW


def test_tracker_uses_capture_time_for_freshness_not_processing_time() -> None:
    clock = FakeClock(10.0)
    tracker = TempleFeatureTracker(clock=clock)
    tracker.update_face(face_observation(sequence=1, captured=1.0, processed=9.99))

    result = tracker.update_hand(
        hand_observation(
            detected_hand(HandSide.RIGHT, (0.2, 0.4)),
            sequence=2,
            captured=9.9,
            processed=9.99,
        )
    )

    assert result.status is TempleFeatureStatus.FACE_UNAVAILABLE


def test_tracker_rejects_stale_future_and_out_of_order_hands() -> None:
    clock = FakeClock(10.0)
    tracker = TempleFeatureTracker(clock=clock)
    tracker.update_face(face_observation(sequence=1, captured=9.9))

    stale = tracker.update_hand(hand_observation(sequence=1, captured=9.7))
    future = tracker.update_hand(hand_observation(sequence=2, captured=10.1))
    out_of_order = tracker.update_hand(hand_observation(sequence=2, captured=9.9))

    assert stale.status is TempleFeatureStatus.HAND_STALE
    assert future.status is TempleFeatureStatus.HAND_STALE
    assert out_of_order.status is TempleFeatureStatus.OUT_OF_ORDER
    assert tracker.latest is future


def test_tracker_rejects_regressing_capture_time_even_with_newer_sequence() -> None:
    clock = FakeClock(10.0)
    tracker = TempleFeatureTracker(clock=clock)
    tracker.update_face(face_observation(sequence=1, captured=9.85))
    first = tracker.update_hand(hand_observation(sequence=1, captured=9.95))
    regressed = tracker.update_hand(hand_observation(sequence=2, captured=9.90))

    assert first.valid_pair
    assert regressed.status is TempleFeatureStatus.OUT_OF_ORDER
    assert tracker.latest is first


def test_nonfinite_capture_time_fails_closed() -> None:
    clock = FakeClock(10.0)
    tracker = TempleFeatureTracker(clock=clock)
    tracker.update_face(face_observation(sequence=1, captured=9.9))

    invalid = tracker.update_hand(hand_observation(sequence=1, captured=float("nan")))
    direct = extract_temple_features(
        face_observation(),
        hand_observation(sequence=2, captured=float("inf")),
        processed_timestamp=10.0,
    )

    assert invalid.status is TempleFeatureStatus.INVALID_TIME
    assert direct.status is TempleFeatureStatus.INVALID_TIME


def test_future_face_is_ignored_and_nonfinite_clock_raises() -> None:
    clock = FakeClock(10.0)
    tracker = TempleFeatureTracker(clock=clock)
    assert tracker.update_face(face_observation(sequence=1, captured=10.1))
    unavailable = tracker.update_hand(hand_observation(sequence=1, captured=9.95))

    assert unavailable.status is TempleFeatureStatus.FACE_UNAVAILABLE

    clock.now = float("nan")
    with pytest.raises(RuntimeError, match="non-finite"):
        tracker.update_hand(hand_observation(sequence=2, captured=10.0))


def test_tracker_expires_valid_state_without_a_new_observation() -> None:
    clock = FakeClock(10.0)
    tracker = TempleFeatureTracker(clock=clock)
    tracker.update_face(face_observation(sequence=1, captured=9.9))
    ready = tracker.update_hand(
        hand_observation(
            detected_hand(HandSide.RIGHT, (0.2, 0.4)),
            sequence=1,
            captured=9.9,
        )
    )

    assert ready.status is TempleFeatureStatus.READY
    assert tracker.expire() is None

    clock.now = 10.2
    expired = tracker.expire()

    assert expired is not None
    assert expired.status is TempleFeatureStatus.EXPIRED
    assert expired.proximities == ()
    assert expired.capture_timestamp == pytest.approx(10.2)


def test_tracker_expires_when_older_face_reaches_timeout() -> None:
    clock = FakeClock(10.0)
    tracker = TempleFeatureTracker(max_pair_skew=0.12, max_age=0.25, clock=clock)
    tracker.update_face(face_observation(sequence=1, captured=9.88))
    ready = tracker.update_hand(hand_observation(sequence=2, captured=10.0))

    assert ready.valid_pair
    assert ready.face_capture_timestamp == pytest.approx(9.88)

    clock.now = 10.129
    assert tracker.expire() is None
    clock.now = 10.131
    expired = tracker.expire()

    assert expired is not None
    assert expired.status is TempleFeatureStatus.EXPIRED


def test_reset_clears_history_and_accepts_a_fresh_lifecycle() -> None:
    clock = FakeClock(10.0)
    tracker = TempleFeatureTracker(clock=clock)
    tracker.update_face(face_observation(sequence=10, captured=9.9))
    tracker.update_hand(hand_observation(sequence=10, captured=9.9))

    tracker.reset()

    assert tracker.latest is None
    assert tracker.update_face(face_observation(sequence=1, captured=9.95))
    fresh = tracker.update_hand(hand_observation(sequence=1, captured=9.95))
    assert fresh.valid_pair
