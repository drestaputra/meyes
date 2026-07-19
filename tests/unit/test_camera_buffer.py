"""Latest-frame buffer tests."""

from __future__ import annotations

import numpy as np

from meyes.camera.buffer import LatestFrameBuffer


def test_latest_frame_overwrites_older_frame() -> None:
    buffer = LatestFrameBuffer()
    first = np.zeros((2, 2, 3), dtype=np.uint8)
    second = np.ones((2, 2, 3), dtype=np.uint8)

    first_packet = buffer.publish(first, 1.0)
    second_packet = buffer.publish(second, 2.0)

    assert first_packet.sequence == 1
    assert second_packet.sequence == 2
    assert buffer.latest() is second_packet


def test_wait_for_new_times_out_without_a_new_sequence() -> None:
    buffer = LatestFrameBuffer()
    packet = buffer.publish(np.zeros((1, 1, 3), dtype=np.uint8), 1.0)

    assert buffer.wait_for_new(after_sequence=packet.sequence, timeout=0.01) is None
