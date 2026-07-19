"""Application shell smoke tests."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import NoReturn

from pytestqt.qtbot import QtBot

from meyes.camera.models import CameraDevice, CameraOptions, FramePacket
from meyes.config.manager import ConfigManager
from meyes.config.models import AppConfig
from meyes.domain.observations import FaceObservation, HandObservation
from meyes.ui.main_window import MainWindow
from meyes.util.paths import AppPaths
from meyes.vision.worker import VisionStatus


class EmptyBackend:
    def enumerate_devices(self, max_index: int = 10) -> list[CameraDevice]:
        return []

    def open(self, options: CameraOptions) -> NoReturn:
        raise RuntimeError("No camera")


class SelectedBackend(EmptyBackend):
    def enumerate_devices(self, max_index: int = 10) -> list[CameraDevice]:
        return [CameraDevice(index=2, name="External camera")]


class EmptyFaceBackend:
    def process(self, packet: FramePacket) -> FaceObservation:
        raise RuntimeError("Face backend is not used in this test")

    def close(self) -> None:
        return None


class EmptyHandBackend:
    def process(self, packet: FramePacket) -> HandObservation:
        raise RuntimeError("Hand backend is not used in this test")

    def close(self) -> None:
        return None


class RecordingFaceBackend(EmptyFaceBackend):
    def __init__(self) -> None:
        self.closed = threading.Event()

    def close(self) -> None:
        self.closed.set()


class RecordingHandBackend(EmptyHandBackend):
    def __init__(self) -> None:
        self.closed = threading.Event()

    def close(self) -> None:
        self.closed.set()


def test_main_window_has_accessible_application_shell(qtbot: QtBot) -> None:
    window = MainWindow(
        AppConfig(),
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
    )
    qtbot.addWidget(window)

    assert window.windowTitle() == "Meyes"
    assert window.minimumWidth() == 900
    assert window.minimumHeight() == 640


def test_discovered_camera_selection_is_persisted(qtbot: QtBot, tmp_path: Path) -> None:
    manager = ConfigManager(AppPaths.under(tmp_path))
    window = MainWindow(
        AppConfig(),
        camera_backend=SelectedBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
    )
    qtbot.addWidget(window)

    qtbot.waitUntil(manager.config_path.exists, timeout=1000)

    assert manager.load().config.camera.camera_index == 2


def test_window_close_stops_both_active_vision_workers(qtbot: QtBot) -> None:
    face = RecordingFaceBackend()
    hand = RecordingHandBackend()
    window = MainWindow(
        AppConfig(),
        camera_backend=EmptyBackend(),
        face_backend_factory=lambda: face,
        hand_backend_factory=lambda: hand,
    )
    qtbot.addWidget(window)
    window._vision_controller.start()
    qtbot.waitUntil(
        lambda: (
            window._vision_controller.status is VisionStatus.RUNNING
            and window._vision_controller.hand_status is VisionStatus.RUNNING
        ),
        timeout=1000,
    )

    window.close()

    assert face.closed.is_set()
    assert hand.closed.is_set()
    assert window._vision_controller.status is VisionStatus.STOPPED
    assert window._vision_controller.hand_status is VisionStatus.STOPPED
    assert not [
        thread.name
        for thread in threading.enumerate()
        if thread.name in {"meyes-face", "meyes-hand"}
    ]
