"""Latest-frame face worker tests without MediaPipe or a webcam."""

from __future__ import annotations

import threading
import time

import numpy as np

from meyes.camera.buffer import LatestFrameBuffer
from meyes.camera.models import FramePacket
from meyes.domain.observations import FaceObservation
from meyes.vision.worker import FaceVisionWorker, VisionStatus


class FakeFaceBackend:
    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.processed_sequences: list[int] = []
        self.closed = False

    def process(self, packet: FramePacket) -> FaceObservation:
        if self.delay:
            time.sleep(self.delay)
        self.processed_sequences.append(packet.sequence)
        return FaceObservation(
            source_sequence=packet.sequence,
            capture_timestamp=packet.capture_timestamp,
            processed_timestamp=packet.capture_timestamp + 0.01,
            face_detected=True,
            left_eye_openness=0.8,
            right_eye_openness=0.9,
        )

    def close(self) -> None:
        self.closed = True


class BlockingFaceBackend(FakeFaceBackend):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def process(self, packet: FramePacket) -> FaceObservation:
        self.started.set()
        if not self.release.wait(timeout=2.0):
            raise TimeoutError("Test did not release the face backend")
        return super().process(packet)


def test_vision_worker_publishes_and_closes_backend() -> None:
    frames = LatestFrameBuffer()
    backend = FakeFaceBackend()
    worker = FaceVisionWorker(frames, lambda: backend, poll_timeout=0.01)

    worker.start()
    frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.0)
    observation = worker.observation_buffer.wait_for_new(timeout=1.0)
    worker.stop()

    assert observation is not None
    assert observation.source_sequence == 1
    assert backend.closed
    assert worker.health.status is VisionStatus.STOPPED


def test_vision_worker_skips_stale_queued_frames() -> None:
    frames = LatestFrameBuffer()
    backend = FakeFaceBackend(delay=0.05)
    worker = FaceVisionWorker(frames, lambda: backend, poll_timeout=0.01)

    worker.start()
    frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.0)
    time.sleep(0.01)
    for timestamp in (2.0, 3.0, 4.0, 5.0):
        frames.publish(np.zeros((1, 1, 3), dtype=np.uint8), timestamp)
    latest = worker.observation_buffer.wait_for_new(after_sequence=1, timeout=1.0)
    worker.stop()

    assert latest is not None
    assert latest.source_sequence == 5
    assert 2 not in backend.processed_sequences
    assert 3 not in backend.processed_sequences
    assert 4 not in backend.processed_sequences


def test_invalidation_discards_in_flight_face_result_until_resumed() -> None:
    frames = LatestFrameBuffer()
    backend = BlockingFaceBackend()
    callbacks: list[FaceObservation] = []
    worker = FaceVisionWorker(
        frames,
        lambda: backend,
        observation_callback=callbacks.append,
        poll_timeout=0.01,
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
    assert backend.closed
