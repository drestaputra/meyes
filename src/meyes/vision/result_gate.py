"""Synchronization gate for invalidating in-flight vision results."""

from __future__ import annotations

import threading
from collections.abc import Callable


class ObservationResultGate:
    """Publish results only while the captured lifecycle generation is active."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._generation = 0
        self._enabled = False

    def enable(self) -> None:
        """Enable publication and begin a fresh lifecycle generation."""
        with self._lock:
            if not self._enabled:
                self._generation += 1
                self._enabled = True

    def token(self) -> int | None:
        """Capture the active generation before starting expensive inference."""
        with self._lock:
            return self._generation if self._enabled else None

    def disable(self, clear: Callable[[], None]) -> None:
        """Invalidate in-flight work and clear published state atomically."""
        with self._lock:
            self._generation += 1
            self._enabled = False
            clear()

    def publish_if_current(
        self,
        token: int | None,
        *,
        cancelled: Callable[[], bool],
        publish: Callable[[], None],
    ) -> bool:
        """Run a publication callback only for the active, non-cancelled generation."""
        with self._lock:
            if token is None or not self._enabled or token != self._generation or cancelled():
                return False
            publish()
            return True
