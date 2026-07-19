"""Qt vision/gesture orchestration tests in no-input safe mode."""

from __future__ import annotations

import threading

import numpy as np
from pytestqt.qtbot import QtBot

from meyes.camera.buffer import LatestFrameBuffer
from meyes.camera.models import FramePacket
from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import FaceObservation
from meyes.vision.controller import VisionController


class SequencedFaceBackend:
    def __init__(self, openness: dict[int, tuple[float, float]]) -> None:
        self._openness = openness
        self.closed = threading.Event()

    def process(self, packet: FramePacket) -> FaceObservation:
        left, right = self._openness[packet.sequence]
        return FaceObservation(
            source_sequence=packet.sequence,
            capture_timestamp=packet.capture_timestamp,
            processed_timestamp=packet.capture_timestamp + 0.01,
            face_detected=True,
            left_eye_openness=left,
            right_eye_openness=right,
        )

    def close(self) -> None:
        self.closed.set()


def publish_and_wait(
    qtbot: QtBot,
    controller: VisionController,
    frames: LatestFrameBuffer,
    timestamp: float,
) -> None:
    with qtbot.waitSignal(controller.observation_changed, timeout=1000):
        frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), timestamp)


def test_controller_emits_semantic_wink_without_action_side_effects(qtbot: QtBot) -> None:
    frames = LatestFrameBuffer()
    backend = SequencedFaceBackend(
        {
            1: (0.9, 0.9),
            2: (0.2, 0.9),
            3: (0.2, 0.9),
        }
    )
    controller = VisionController(frames, lambda: backend, GestureSettings())
    events: list[GestureEvent] = []
    controller.event_detected.connect(events.append)
    controller.start()

    publish_and_wait(qtbot, controller, frames, 1.00)
    publish_and_wait(qtbot, controller, frames, 1.05)
    with qtbot.waitSignal(controller.event_detected, timeout=1000):
        frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.20)
    controller.stop()

    assert [event.type for event in events] == [GestureEventType.LEFT_WINK]
    assert backend.closed.is_set()


def test_suspend_clears_candidate_and_observation(qtbot: QtBot) -> None:
    frames = LatestFrameBuffer()
    backend = SequencedFaceBackend({1: (0.9, 0.9), 2: (0.2, 0.9), 3: (0.2, 0.9)})
    controller = VisionController(frames, lambda: backend, GestureSettings())
    events: list[GestureEvent] = []
    controller.event_detected.connect(events.append)
    controller.start()

    publish_and_wait(qtbot, controller, frames, 1.00)
    publish_and_wait(qtbot, controller, frames, 1.05)
    with qtbot.waitSignal(controller.observation_cleared, timeout=1000):
        controller.suspend()
    controller.start()
    publish_and_wait(qtbot, controller, frames, 1.20)
    controller.stop()

    assert events == []
