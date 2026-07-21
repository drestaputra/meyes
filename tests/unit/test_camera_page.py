"""Dedicated camera settings and health view tests."""

from __future__ import annotations

from typing import NoReturn, TypeVar

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton, QSpinBox
from pytestqt.qtbot import QtBot

from meyes.camera.controller import CameraController
from meyes.camera.models import CameraDevice, CameraHealth, CameraOptions, CameraStatus
from meyes.config.models import CameraSettings
from meyes.ui.camera_page import CameraPage, CameraSettingsSaveResult

QObjectType = TypeVar("QObjectType", bound=QObject)


class EmptyBackend:
    def enumerate_devices(self, max_index: int = 10) -> list[CameraDevice]:
        return []

    def open(self, options: CameraOptions) -> NoReturn:
        raise RuntimeError("not used")


def _child(page: CameraPage, widget_type: type[QObjectType], name: str) -> QObjectType:
    widget = page.findChild(widget_type, name)
    assert widget is not None
    return widget


def test_camera_page_starts_clean_and_does_not_start_capture(qtbot: QtBot) -> None:
    settings = CameraSettings(width=1280, height=720, target_fps=60, mirror=False)
    controller = CameraController(EmptyBackend(), settings)
    page = CameraPage(
        controller,
        lambda draft: CameraSettingsSaveResult(True, "saved", draft),
    )
    qtbot.addWidget(page)

    assert _child(page, QSpinBox, "cameraWidthInput").value() == 1280
    assert _child(page, QSpinBox, "cameraHeightInput").value() == 720
    assert _child(page, QSpinBox, "cameraTargetFpsInput").value() == 60
    assert _child(page, QCheckBox, "cameraMirrorInput").isChecked() is False
    assert _child(page, QPushButton, "cameraSettingsSaveButton").isEnabled() is False
    assert _child(page, QPushButton, "cameraSettingsStopButton").isHidden() is True
    assert controller.status is CameraStatus.STOPPED
    controller.shutdown()


def test_camera_page_saves_complete_stopped_capture_draft(qtbot: QtBot) -> None:
    controller = CameraController(EmptyBackend(), CameraSettings(camera_index=3))
    calls: list[CameraSettings] = []

    def save(settings: CameraSettings) -> CameraSettingsSaveResult:
        calls.append(settings)
        return CameraSettingsSaveResult(True, "Camera settings saved.", settings)

    page = CameraPage(controller, save)
    qtbot.addWidget(page)
    _child(page, QSpinBox, "cameraWidthInput").setValue(1920)
    _child(page, QSpinBox, "cameraHeightInput").setValue(1080)
    _child(page, QSpinBox, "cameraTargetFpsInput").setValue(30)
    save_button = _child(page, QPushButton, "cameraSettingsSaveButton")

    save_button.click()

    assert calls == [CameraSettings(camera_index=3, width=1920, height=1080, target_fps=30)]
    assert save_button.isEnabled() is False
    feedback = _child(page, QLabel, "cameraSettingsFeedback")
    assert feedback.text() == "Camera settings saved."
    assert feedback.property("feedbackStatus") == "success"
    controller.shutdown()


def test_running_health_blocks_save_without_discarding_draft(qtbot: QtBot) -> None:
    controller = CameraController(EmptyBackend(), CameraSettings())
    page = CameraPage(
        controller,
        lambda draft: CameraSettingsSaveResult(True, "saved", draft),
    )
    qtbot.addWidget(page)
    _child(page, QSpinBox, "cameraWidthInput").setValue(1280)

    controller.health_changed.emit(
        CameraHealth(
            CameraStatus.RUNNING,
            "Camera is running",
            camera_index=0,
            measured_fps=29.5,
        )
    )

    assert _child(page, QPushButton, "cameraSettingsSaveButton").isEnabled() is False
    assert _child(page, QPushButton, "cameraSettingsStopButton").isHidden() is False
    assert _child(page, QSpinBox, "cameraWidthInput").value() == 1280
    assert "stop camera" in _child(page, QLabel, "cameraSettingsDirtyStatus").text()
    assert _child(page, QLabel, "cameraSettingsHealthFps").text() == "29.5"
    controller.shutdown()


def test_external_clean_setting_change_updates_visible_fields(qtbot: QtBot) -> None:
    controller = CameraController(EmptyBackend(), CameraSettings())
    page = CameraPage(
        controller,
        lambda draft: CameraSettingsSaveResult(True, "saved", draft),
    )
    qtbot.addWidget(page)

    controller.apply_settings(CameraSettings(width=800, height=600, target_fps=24, mirror=False))

    assert _child(page, QSpinBox, "cameraWidthInput").value() == 800
    assert _child(page, QSpinBox, "cameraHeightInput").value() == 600
    assert _child(page, QSpinBox, "cameraTargetFpsInput").value() == 24
    assert _child(page, QCheckBox, "cameraMirrorInput").isChecked() is False
    controller.shutdown()
