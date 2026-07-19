"""Camera domain models with no Qt dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

FrameArray = NDArray[np.uint8]


class CameraStatus(StrEnum):
    """Explicit capture lifecycle states exposed to the UI."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    RECOVERING = "recovering"
    ERROR = "error"
    STOPPING = "stopping"


@dataclass(frozen=True, slots=True)
class CameraDevice:
    """A camera exposed for selection."""

    index: int
    name: str


@dataclass(frozen=True, slots=True)
class CameraOptions:
    """Capture options independent of config persistence."""

    camera_index: int = 0
    width: int = 640
    height: int = 480
    target_fps: int = 30


@dataclass(frozen=True, slots=True)
class FramePacket:
    """One immutable-by-convention frame plus timing metadata."""

    sequence: int
    capture_timestamp: float
    frame: FrameArray


@dataclass(frozen=True, slots=True)
class CameraHealth:
    """Latest capture health snapshot."""

    status: CameraStatus = CameraStatus.STOPPED
    message: str = "Camera is stopped"
    camera_index: int | None = None
    measured_fps: float = 0.0
    failure_count: int = 0
    last_error: str | None = None
