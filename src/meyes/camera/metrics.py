"""Low-overhead rolling capture metrics."""

from __future__ import annotations

from collections import deque


class FrameRateMeter:
    """Estimate effective FPS from recent monotonic timestamps."""

    def __init__(self, window_size: int = 30) -> None:
        if window_size < 2:
            raise ValueError("window_size must be at least 2")
        self._timestamps: deque[float] = deque(maxlen=window_size)

    def tick(self, timestamp: float) -> float:
        """Record a frame timestamp and return the current FPS estimate."""
        self._timestamps.append(timestamp)
        if len(self._timestamps) < 2:
            return 0.0
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return 0.0
        return (len(self._timestamps) - 1) / elapsed

    def reset(self) -> None:
        """Clear the measurement window after pause or reconnect."""
        self._timestamps.clear()
