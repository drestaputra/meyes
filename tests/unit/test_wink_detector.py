"""Wink state-machine tests from recorded normalized observations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict, cast

from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import FaceObservation
from meyes.gestures.engine import GestureEngine
from meyes.gestures.wink_detector import WinkDetector, WinkDetectorSettings

FIXTURES = Path(__file__).parents[1] / "fixtures" / "observation_sequences"


class Sample(TypedDict):
    t_ms: int
    left: float
    right: float


def observation(sequence: int, t_ms: int, left: float, right: float) -> FaceObservation:
    timestamp = t_ms / 1000.0
    return FaceObservation(
        source_sequence=sequence,
        capture_timestamp=timestamp,
        processed_timestamp=timestamp + 0.01,
        face_detected=True,
        left_eye_openness=left,
        right_eye_openness=right,
    )


def run_fixture(name: str, detector: WinkDetector | None = None) -> list[GestureEvent]:
    samples = cast(
        list[Sample],
        json.loads((FIXTURES / name).read_text(encoding="utf-8")),
    )
    events: list[GestureEvent] = []
    active_detector = detector or WinkDetector()
    for sequence, sample in enumerate(samples, start=1):
        events.extend(
            active_detector.update(
                observation(
                    sequence,
                    sample["t_ms"],
                    sample["left"],
                    sample["right"],
                )
            )
        )
    return events


def test_both_eye_blink_emits_no_wink() -> None:
    assert run_fixture("both_eye_blink.json") == []


def test_left_wink_emits_once_for_sustained_closure() -> None:
    events = run_fixture("left_wink.json")

    assert [event.type for event in events] == [GestureEventType.LEFT_WINK]
    assert events[0].duration_ms >= 140


def test_right_wink_emits_once() -> None:
    events = run_fixture("right_wink.json")

    assert [event.type for event in events] == [GestureEventType.RIGHT_WINK]


def test_wink_started_during_cooldown_is_not_queued() -> None:
    detector = WinkDetector(WinkDetectorSettings(cooldown=0.5))
    samples = [
        (0, 0.9, 0.9),
        (50, 0.2, 0.9),
        (200, 0.2, 0.9),
        (250, 0.9, 0.9),
        (300, 0.2, 0.9),
        (600, 0.2, 0.9),
        (650, 0.9, 0.9),
    ]
    events = [
        event
        for sequence, (t_ms, left, right) in enumerate(samples, start=1)
        for event in detector.update(observation(sequence, t_ms, left, right))
    ]

    assert [event.type for event in events] == [GestureEventType.LEFT_WINK]


def test_tracking_loss_cancels_candidate() -> None:
    detector = WinkDetector()
    detector.update(observation(1, 0, 0.9, 0.9))
    detector.update(observation(2, 50, 0.2, 0.9))
    lost = FaceObservation(
        source_sequence=3,
        capture_timestamp=0.10,
        processed_timestamp=0.11,
        face_detected=False,
    )
    assert detector.update(lost) == ()

    events = detector.update(observation(4, 210, 0.2, 0.9))

    assert events == ()


def test_non_monotonic_observation_is_ignored() -> None:
    detector = WinkDetector()

    detector.update(observation(1, 100, 0.9, 0.9))

    assert detector.update(observation(2, 90, 0.2, 0.9)) == ()


def test_gap_longer_than_tracking_timeout_restarts_candidate() -> None:
    detector = WinkDetector(WinkDetectorSettings(tracking_timeout=0.2))

    detector.update(observation(1, 0, 0.9, 0.9))
    detector.update(observation(2, 50, 0.2, 0.9))

    assert detector.update(observation(3, 400, 0.2, 0.9)) == ()


def test_closure_longer_than_maximum_is_not_a_wink() -> None:
    detector = WinkDetector(WinkDetectorSettings(max_duration=0.5))

    detector.update(observation(1, 0, 0.9, 0.9))
    detector.update(observation(2, 50, 0.2, 0.9))

    assert detector.update(observation(3, 600, 0.2, 0.9)) == ()


def test_gesture_engine_converts_persisted_millisecond_settings() -> None:
    engine = GestureEngine.from_settings(
        GestureSettings(wink_min_duration_ms=200, wink_max_duration_ms=700)
    )

    assert engine.wink_detector.settings.min_duration == 0.2
    assert engine.wink_detector.settings.max_duration == 0.7
