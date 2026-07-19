"""Thread-safe latest-frame-only transport."""

from __future__ import annotations

import threading

from meyes.camera.models import FrameArray, FramePacket


class LatestFrameBuffer:
    """Store only the newest camera frame to prevent latency queues."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._latest: FramePacket | None = None
        self._sequence = 0

    def publish(self, frame: FrameArray, capture_timestamp: float) -> FramePacket:
        """Atomically replace the previous frame and wake consumers."""
        with self._condition:
            self._sequence += 1
            packet = FramePacket(
                sequence=self._sequence,
                capture_timestamp=capture_timestamp,
                frame=frame,
            )
            self._latest = packet
            self._condition.notify_all()
            return packet

    def latest(self) -> FramePacket | None:
        """Return the newest frame without copying image memory."""
        with self._condition:
            return self._latest

    def wait_for_new(
        self, after_sequence: int = 0, timeout: float | None = None
    ) -> FramePacket | None:
        """Wait until a newer sequence is available or timeout expires."""
        with self._condition:
            self._condition.wait_for(
                lambda: self._latest is not None and self._latest.sequence > after_sequence,
                timeout=timeout,
            )
            if self._latest is None or self._latest.sequence <= after_sequence:
                return None
            return self._latest

    def clear(self) -> None:
        """Drop the current frame while preserving sequence monotonicity."""
        with self._condition:
            self._latest = None
            self._condition.notify_all()
