"""OpenCV camera backend for Windows."""

from __future__ import annotations

import os
from typing import cast

import cv2

from meyes.camera.interface import CameraCapture
from meyes.camera.models import CameraDevice, CameraOptions, FrameArray


class CameraOpenError(RuntimeError):
    """Raised when OpenCV cannot open the selected camera."""


class OpenCVCapture:
    """Thin owned wrapper around `cv2.VideoCapture`."""

    def __init__(self, capture: cv2.VideoCapture) -> None:
        self._capture = capture

    def read(self) -> tuple[bool, FrameArray | None]:
        """Read one BGR frame."""
        ok, frame = self._capture.read()
        if not ok or frame is None:
            return False, None
        return True, cast(FrameArray, frame)

    def release(self) -> None:
        """Release the native camera handle."""
        self._capture.release()


class OpenCVCameraBackend:
    """Create and enumerate OpenCV camera captures."""

    def enumerate_devices(self, max_index: int = 10) -> list[CameraDevice]:
        """Probe a bounded set of camera indexes.

        Enumeration is explicit because probing may briefly activate a webcam.
        """
        devices: list[CameraDevice] = []
        for index in range(max_index):
            capture = self._create_video_capture(index)
            try:
                if capture.isOpened():
                    devices.append(CameraDevice(index=index, name=f"Camera {index + 1}"))
            finally:
                capture.release()
        return devices

    def open(self, options: CameraOptions) -> CameraCapture:
        """Open and configure one camera or raise a recoverable error."""
        capture = self._create_video_capture(options.camera_index)
        if not capture.isOpened():
            capture.release()
            raise CameraOpenError(f"Unable to open camera index {options.camera_index}")

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(options.width))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(options.height))
        capture.set(cv2.CAP_PROP_FPS, float(options.target_fps))
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1.0)
        return OpenCVCapture(capture)

    @staticmethod
    def _create_video_capture(index: int) -> cv2.VideoCapture:
        if os.name == "nt":
            return cv2.VideoCapture(index, cv2.CAP_DSHOW)
        return cv2.VideoCapture(index)
