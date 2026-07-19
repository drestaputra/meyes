"""Qt camera bridge tests with no physical webcam."""

from __future__ import annotations

from collections import deque

import numpy as np
from PySide6.QtGui import QColor, QImage
from pytestqt.qtbot import QtBot

from meyes.camera.controller import CameraController
from meyes.camera.models import CameraDevice, CameraOptions, FrameArray
from meyes.config.models import CameraSettings


class PreviewCapture:
    def __init__(self, frames: list[FrameArray]) -> None:
        self._frames = deque(frames)
        self.released = False

    def read(self) -> tuple[bool, FrameArray | None]:
        if self._frames:
            return True, self._frames.popleft()
        return False, None

    def release(self) -> None:
        self.released = True


class PreviewBackend:
    def __init__(self, capture: PreviewCapture) -> None:
        self.capture = capture

    def enumerate_devices(self, max_index: int = 10) -> list[CameraDevice]:
        return [CameraDevice(index=0, name="Test camera")]

    def open(self, options: CameraOptions) -> PreviewCapture:
        return self.capture


class SwitchingBackend:
    def __init__(self, captures: list[PreviewCapture]) -> None:
        self._captures = deque(captures)
        self.opened_indexes: list[int] = []

    def enumerate_devices(self, max_index: int = 10) -> list[CameraDevice]:
        return [CameraDevice(0, "First"), CameraDevice(1, "Second")]

    def open(self, options: CameraOptions) -> PreviewCapture:
        self.opened_indexes.append(options.camera_index)
        return self._captures.popleft()


def test_controller_enumerates_without_blocking_qt(qtbot: QtBot) -> None:
    capture = PreviewCapture([])
    controller = CameraController(PreviewBackend(capture), CameraSettings())

    with qtbot.waitSignal(controller.devices_changed, timeout=1000) as signal:
        controller.refresh_devices()

    devices = signal.args[0]
    assert isinstance(devices, list)
    assert devices == [CameraDevice(index=0, name="Test camera")]
    controller.shutdown()


def test_preview_mirroring_does_not_modify_processing_frame(qtbot: QtBot) -> None:
    original = np.array([[[0, 0, 255], [255, 0, 0]]], dtype=np.uint8)
    capture = PreviewCapture([original])
    controller = CameraController(
        PreviewBackend(capture),
        CameraSettings(mirror=True),
        preview_interval_ms=5,
    )

    with qtbot.waitSignal(controller.preview_changed, timeout=1000) as signal:
        controller.start()

    image = signal.args[0]
    assert isinstance(image, QImage)
    assert image.pixelColor(0, 0) == QColor("blue")
    assert image.pixelColor(1, 0) == QColor("red")
    assert original[0, 0].tolist() == [0, 0, 255]
    controller.shutdown()


def test_mirror_setting_emits_persistable_settings(qtbot: QtBot) -> None:
    controller = CameraController(PreviewBackend(PreviewCapture([])), CameraSettings())

    with qtbot.waitSignal(controller.settings_changed, timeout=1000) as signal:
        controller.set_mirror(False)

    settings = signal.args[0]
    assert isinstance(settings, CameraSettings)
    assert settings.mirror is False
    controller.shutdown()


def test_stopped_camera_can_switch_without_leaking_previous_capture(qtbot: QtBot) -> None:
    first = PreviewCapture([np.zeros((1, 1, 3), dtype=np.uint8)])
    second = PreviewCapture([np.ones((1, 1, 3), dtype=np.uint8)])
    backend = SwitchingBackend([first, second])
    controller = CameraController(backend, CameraSettings(), preview_interval_ms=5)

    with qtbot.waitSignal(controller.preview_changed, timeout=1000):
        controller.start()
    controller.stop()
    controller.select_camera(1)
    with qtbot.waitSignal(controller.preview_changed, timeout=1000):
        controller.start()
    controller.shutdown()

    assert backend.opened_indexes == [0, 1]
    assert first.released
    assert second.released
