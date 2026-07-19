"""Replaceable camera backend protocols."""

from __future__ import annotations

from typing import Protocol

from meyes.camera.models import CameraDevice, CameraOptions, FrameArray


class CameraCapture(Protocol):
    """Opened capture handle owned by a camera worker."""

    def read(self) -> tuple[bool, FrameArray | None]: ...

    def release(self) -> None: ...


class CameraBackend(Protocol):
    """Backend contract used by the worker and device selector."""

    def enumerate_devices(self, max_index: int = 10) -> list[CameraDevice]: ...

    def open(self, options: CameraOptions) -> CameraCapture: ...
