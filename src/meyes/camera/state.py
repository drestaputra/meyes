"""Validated camera lifecycle state machine."""

from __future__ import annotations

import threading

from meyes.camera.models import CameraStatus

_ALLOWED_TRANSITIONS: dict[CameraStatus, frozenset[CameraStatus]] = {
    CameraStatus.STOPPED: frozenset({CameraStatus.STARTING}),
    CameraStatus.STARTING: frozenset(
        {
            CameraStatus.RUNNING,
            CameraStatus.PAUSED,
            CameraStatus.RECOVERING,
            CameraStatus.ERROR,
            CameraStatus.STOPPING,
        }
    ),
    CameraStatus.RUNNING: frozenset(
        {
            CameraStatus.PAUSED,
            CameraStatus.RECOVERING,
            CameraStatus.ERROR,
            CameraStatus.STOPPING,
        }
    ),
    CameraStatus.PAUSED: frozenset({CameraStatus.STARTING, CameraStatus.STOPPING}),
    CameraStatus.RECOVERING: frozenset(
        {
            CameraStatus.STARTING,
            CameraStatus.PAUSED,
            CameraStatus.ERROR,
            CameraStatus.STOPPING,
        }
    ),
    CameraStatus.ERROR: frozenset(
        {
            CameraStatus.STARTING,
            CameraStatus.PAUSED,
            CameraStatus.STOPPING,
            CameraStatus.STOPPED,
        }
    ),
    CameraStatus.STOPPING: frozenset({CameraStatus.STOPPED, CameraStatus.ERROR}),
}


class InvalidCameraTransition(RuntimeError):
    """Raised when lifecycle code attempts an unsafe state jump."""


class CameraStateMachine:
    """Thread-safe transition validation and status waiting."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._status = CameraStatus.STOPPED

    @property
    def status(self) -> CameraStatus:
        """Return the current lifecycle state."""
        with self._condition:
            return self._status

    def transition(self, target: CameraStatus) -> CameraStatus:
        """Move to an allowed state and wake waiters."""
        with self._condition:
            current = self._status
            if target == current:
                return current
            if target not in _ALLOWED_TRANSITIONS[current]:
                raise InvalidCameraTransition(
                    f"Cannot transition camera from {current} to {target}"
                )
            self._status = target
            self._condition.notify_all()
            return target

    def wait_for(self, target: CameraStatus, timeout: float | None = None) -> bool:
        """Wait for an exact state and report whether it was reached."""
        with self._condition:
            return self._condition.wait_for(lambda: self._status is target, timeout=timeout)
