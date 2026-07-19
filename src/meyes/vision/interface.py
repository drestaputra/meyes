"""Replaceable vision backend contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from meyes.camera.models import FramePacket
from meyes.domain.observations import FaceObservation


class FaceObservationBackend(Protocol):
    """Convert a camera frame into one normalized face observation."""

    def process(self, packet: FramePacket) -> FaceObservation: ...

    def close(self) -> None: ...


FaceBackendFactory = Callable[[], FaceObservationBackend]
