"""Thread-safe latest face-observation transport."""

from __future__ import annotations

import threading

from meyes.domain.observations import FaceObservation


class LatestFaceObservationBuffer:
    """Store only the newest observation for gestures and diagnostics."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._latest: FaceObservation | None = None

    def publish(self, observation: FaceObservation) -> None:
        """Replace the previous observation and wake consumers."""
        with self._condition:
            self._latest = observation
            self._condition.notify_all()

    def latest(self) -> FaceObservation | None:
        """Return the newest observation."""
        with self._condition:
            return self._latest

    def wait_for_new(
        self, after_sequence: int = 0, timeout: float | None = None
    ) -> FaceObservation | None:
        """Wait for an observation sourced from a newer frame."""
        with self._condition:
            self._condition.wait_for(
                lambda: self._latest is not None and self._latest.source_sequence > after_sequence,
                timeout=timeout,
            )
            if self._latest is None or self._latest.source_sequence <= after_sequence:
                return None
            return self._latest

    def clear(self) -> None:
        """Drop stale face state after shutdown or camera loss."""
        with self._condition:
            self._latest = None
            self._condition.notify_all()
