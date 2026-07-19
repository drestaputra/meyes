"""Lower-cadence hand worker tests without MediaPipe or a webcam."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from meyes.camera.buffer import LatestFrameBuffer
from meyes.camera.models import FramePacket
from meyes.domain.observations import DetectedHand, HandObservation, HandSide, NormalizedPoint
from meyes.vision.hand_worker import HandVisionWorker
from meyes.vision.worker import VisionStatus


class FakeHandBackend:
    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.processed_sequences: list[int] = []
        self.close_count = 0

    def process(self, packet: FramePacket) -> HandObservation:
        if self.delay:
            time.sleep(self.delay)
        self.processed_sequences.append(packet.sequence)
        return HandObservation(
            source_sequence=packet.sequence,
            capture_timestamp=packet.capture_timestamp,
            processed_timestamp=packet.capture_timestamp + 0.02,
            hands=(
                DetectedHand(
                    side=HandSide.RIGHT,
                    confidence=0.9,
                    landmarks=(NormalizedPoint(0.4, 0.5),),
                ),
            ),
        )

    def close(self) -> None:
        self.close_count += 1


class BlockingHandBackend(FakeHandBackend):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def process(self, packet: FramePacket) -> HandObservation:
        self.started.set()
        if not self.release.wait(timeout=2.0):
            raise TimeoutError("Test did not release the hand backend")
        return super().process(packet)


def test_hand_worker_publishes_and_closes_backend() -> None:
    frames = LatestFrameBuffer()
    backend = FakeHandBackend()
    worker = HandVisionWorker(frames, lambda: backend, poll_timeout=0.01)

    worker.start()
    frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.0)
    observation = worker.observation_buffer.wait_for_new(timeout=1.0)
    worker.stop()

    assert observation is not None
    assert observation.source_sequence == 1
    assert backend.close_count == 1
    assert worker.health.status is VisionStatus.STOPPED


def test_hand_worker_uses_wall_clock_cadence_and_newest_pending_frame() -> None:
    frames = LatestFrameBuffer()
    backend = FakeHandBackend()
    worker = HandVisionWorker(frames, lambda: backend, target_fps=20.0, poll_timeout=0.005)

    worker.start()
    frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.00)
    assert worker.observation_buffer.wait_for_new(timeout=1.0) is not None
    frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1_000_000.0)
    frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), -1_000_000.0)

    assert worker.observation_buffer.wait_for_new(after_sequence=1, timeout=0.02) is None
    latest = worker.observation_buffer.wait_for_new(after_sequence=1, timeout=1.0)
    worker.stop()

    assert latest is not None
    assert latest.source_sequence == 3
    assert backend.processed_sequences == [1, 3]


def test_hand_worker_skips_frames_queued_during_inference() -> None:
    frames = LatestFrameBuffer()
    backend = FakeHandBackend(delay=0.05)
    worker = HandVisionWorker(frames, lambda: backend, target_fps=30.0, poll_timeout=0.005)

    worker.start()
    frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.00)
    time.sleep(0.01)
    for timestamp in (1.04, 1.08, 1.12, 1.16):
        frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), timestamp)
    latest = worker.observation_buffer.wait_for_new(after_sequence=1, timeout=1.0)
    worker.stop()

    assert latest is not None
    assert latest.source_sequence == 5
    assert backend.processed_sequences == [1, 5]


@pytest.mark.parametrize("target_fps", [0.0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_hand_worker_rejects_invalid_target_fps(target_fps: float) -> None:
    with pytest.raises(ValueError, match="finite and greater than zero"):
        HandVisionWorker(LatestFrameBuffer(), FakeHandBackend, target_fps=target_fps)


def test_invalidation_discards_in_flight_result_until_resumed() -> None:
    frames = LatestFrameBuffer()
    backend = BlockingHandBackend()
    callbacks: list[HandObservation] = []
    worker = HandVisionWorker(
        frames,
        lambda: backend,
        observation_callback=callbacks.append,
        poll_timeout=0.005,
    )

    worker.start()
    frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.0)
    assert backend.started.wait(timeout=1.0)
    worker.invalidate_observations()
    backend.release.set()
    time.sleep(0.05)

    assert worker.observation_buffer.latest() is None
    assert callbacks == []

    worker.resume_observations()
    frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.1)
    resumed = worker.observation_buffer.wait_for_new(timeout=1.0)
    worker.stop()

    assert resumed is not None
    assert resumed.source_sequence == 2
    assert backend.close_count == 1


def test_stop_discards_in_flight_result_and_closes_once() -> None:
    frames = LatestFrameBuffer()
    backend = BlockingHandBackend()
    callbacks: list[HandObservation] = []
    statuses: list[VisionStatus] = []
    worker = HandVisionWorker(
        frames,
        lambda: backend,
        observation_callback=callbacks.append,
        health_callback=lambda health: statuses.append(health.status),
        poll_timeout=0.005,
    )

    worker.start()
    frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.0)
    assert backend.started.wait(timeout=1.0)
    stopper = threading.Thread(target=worker.stop)
    stopper.start()
    time.sleep(0.02)
    backend.release.set()
    stopper.join(timeout=1.0)

    assert not stopper.is_alive()
    assert callbacks == []
    assert worker.observation_buffer.latest() is None
    assert backend.close_count == 1
    assert statuses[-2:] == [VisionStatus.STOPPING, VisionStatus.STOPPED]
