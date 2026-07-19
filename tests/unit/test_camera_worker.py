"""Camera worker tests with a deterministic fake backend."""

from __future__ import annotations

import threading
from collections import deque

import numpy as np

from meyes.camera.models import CameraDevice, CameraOptions, CameraStatus, FrameArray
from meyes.camera.worker import CameraWorker


class FakeCapture:
    def __init__(self, frames: list[FrameArray]) -> None:
        self._frames = deque(frames)
        self.released = False

    def read(self) -> tuple[bool, FrameArray | None]:
        if self._frames:
            return True, self._frames.popleft()
        return False, None

    def release(self) -> None:
        self.released = True


class BlockingCapture:
    def __init__(self) -> None:
        self.read_started = threading.Event()
        self.release_requested = threading.Event()

    def read(self) -> tuple[bool, FrameArray | None]:
        self.read_started.set()
        self.release_requested.wait(timeout=2.0)
        return False, None

    def release(self) -> None:
        self.release_requested.set()


class FakeBackend:
    def __init__(self, captures: list[FakeCapture | BlockingCapture | Exception]) -> None:
        self._captures = deque(captures)
        self.open_count = 0

    def enumerate_devices(self, max_index: int = 10) -> list[CameraDevice]:
        return [CameraDevice(0, "Fake camera")]

    def open(self, options: CameraOptions) -> FakeCapture | BlockingCapture:
        self.open_count += 1
        if not self._captures:
            raise RuntimeError("No fake capture available")
        capture = self._captures.popleft()
        if isinstance(capture, Exception):
            raise capture
        return capture


def test_worker_publishes_latest_frame_and_stops_cleanly() -> None:
    frame_ready = threading.Event()
    capture = FakeCapture([np.full((2, 2, 3), 7, dtype=np.uint8)])
    worker = CameraWorker(
        FakeBackend([capture]),
        CameraOptions(),
        health_callback=lambda health: (
            frame_ready.set()
            if health.status is CameraStatus.RUNNING and health.measured_fps >= 0
            else None
        ),
        retry_delay=0.01,
    )

    worker.start()
    packet = worker.frame_buffer.wait_for_new(timeout=1.0)
    worker.stop()

    assert frame_ready.is_set()
    assert packet is not None
    assert packet.frame[0, 0, 0] == 7
    assert capture.released
    assert worker.status is CameraStatus.STOPPED


def test_worker_recovers_after_open_failure() -> None:
    capture = FakeCapture([np.ones((1, 1, 3), dtype=np.uint8)])
    backend = FakeBackend([RuntimeError("camera unavailable"), capture])
    worker = CameraWorker(backend, CameraOptions(), retry_delay=0.01)

    worker.start()
    packet = worker.frame_buffer.wait_for_new(timeout=1.0)
    worker.stop()

    assert packet is not None
    assert backend.open_count >= 2
    assert worker.status is CameraStatus.STOPPED


def test_pause_releases_capture_and_resume_reopens() -> None:
    first = FakeCapture([np.zeros((1, 1, 3), dtype=np.uint8)])
    second = FakeCapture([np.ones((1, 1, 3), dtype=np.uint8)])
    worker = CameraWorker(FakeBackend([first, second]), CameraOptions(), retry_delay=0.01)

    worker.start()
    first_packet = worker.frame_buffer.wait_for_new(timeout=1.0)
    worker.pause()
    assert worker.wait_for_status(CameraStatus.PAUSED)
    worker.resume()
    second_packet = worker.frame_buffer.wait_for_new(
        after_sequence=first_packet.sequence if first_packet else 0,
        timeout=1.0,
    )
    worker.stop()

    assert first.released
    assert second_packet is not None
    assert second_packet.frame[0, 0, 0] == 1


def test_stop_releases_a_capture_to_unblock_read() -> None:
    capture = BlockingCapture()
    worker = CameraWorker(FakeBackend([capture]), CameraOptions(), retry_delay=0.01)

    worker.start()
    assert capture.read_started.wait(timeout=1.0)
    worker.stop(timeout=1.0)

    assert capture.release_requested.is_set()
    assert worker.status is CameraStatus.STOPPED
