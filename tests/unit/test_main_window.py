"""Application shell smoke tests."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

from pytestqt.qtbot import QtBot

from meyes.camera.models import CameraDevice, CameraOptions, FramePacket
from meyes.config.manager import ConfigManager
from meyes.config.models import AppConfig
from meyes.domain.observations import FaceObservation
from meyes.ui.main_window import MainWindow
from meyes.util.paths import AppPaths


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


def test_main_window_has_accessible_application_shell(qtbot: QtBot) -> None:
    window = MainWindow(
        AppConfig(),
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
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
        config_manager=manager,
    )
    qtbot.addWidget(window)

    qtbot.waitUntil(manager.config_path.exists, timeout=1000)

    assert manager.load().config.camera.camera_index == 2
