"""Optional system-tray lifecycle control tests."""

from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from meyes.camera.models import CameraStatus
from meyes.ui.live_input import LiveInputState
from meyes.ui.system_tray import SystemTrayController


def _action(controller: SystemTrayController, name: str) -> QAction:
    action = controller.findChild(QAction, name)
    assert action is not None
    return action


def test_tray_actions_follow_camera_and_live_state_without_showing_icon(
    qapp: QApplication,
) -> None:
    del qapp
    calls: list[str] = []
    controller = SystemTrayController(
        QIcon(),
        show_window=lambda: calls.append("show"),
        pause_tracking=lambda: calls.append("pause"),
        resume_tracking=lambda: calls.append("resume"),
        return_to_safe_mode=lambda: calls.append("safe"),
        quit_application=lambda: calls.append("quit"),
        show_icon=False,
    )
    tracking = _action(controller, "trayTrackingAction")
    safe = _action(controller, "traySafeModeAction")
    status = _action(controller, "trayStatusAction")

    assert controller.icon.isVisible() is False
    assert tracking.isEnabled() is False
    assert safe.isEnabled() is False
    controller.observe_camera_status(CameraStatus.RUNNING)
    assert tracking.text() == "Pause tracking"
    tracking.trigger()
    controller.observe_camera_status(CameraStatus.PAUSED)
    assert tracking.text() == "Resume tracking"
    tracking.trigger()
    controller.observe_live_input_state(LiveInputState.ARMED)
    assert safe.isEnabled() is True
    assert "LIVE INPUT" in status.text()
    safe.trigger()

    assert calls == ["pause", "resume", "safe"]
    controller.close()


def test_tray_show_quit_activation_and_close_are_bounded(qapp: QApplication) -> None:
    del qapp
    calls: list[str] = []
    controller = SystemTrayController(
        QIcon(),
        show_window=lambda: calls.append("show"),
        pause_tracking=lambda: calls.append("pause"),
        resume_tracking=lambda: calls.append("resume"),
        return_to_safe_mode=lambda: calls.append("safe"),
        quit_application=lambda: calls.append("quit"),
        show_icon=False,
    )

    _action(controller, "trayShowAction").trigger()
    controller.icon.activated.emit(QSystemTrayIcon.ActivationReason.DoubleClick)
    _action(controller, "trayQuitAction").trigger()

    assert calls == ["show", "show", "quit"]
    controller.close()
    controller.close()
    assert _action(controller, "trayShowAction").isEnabled() is False
    assert _action(controller, "trayQuitAction").isEnabled() is False
