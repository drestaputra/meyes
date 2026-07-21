"""Optional Windows system-tray controls for existing safe lifecycle operations."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from meyes.camera.models import CameraStatus
from meyes.ui.live_input import LiveInputState

ActionCallback = Callable[[], object]


class SystemTrayController(QObject):
    """Expose bounded lifecycle actions without changing window-close semantics."""

    def __init__(
        self,
        icon: QIcon,
        *,
        show_window: ActionCallback,
        pause_tracking: ActionCallback,
        resume_tracking: ActionCallback,
        return_to_safe_mode: ActionCallback,
        quit_application: ActionCallback,
        show_icon: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        callbacks = (
            show_window,
            pause_tracking,
            resume_tracking,
            return_to_safe_mode,
            quit_application,
        )
        if not isinstance(icon, QIcon):
            raise TypeError("Expected QIcon")
        if not all(callable(callback) for callback in callbacks):
            raise TypeError("System tray callbacks must be callable")
        if not isinstance(show_icon, bool):
            raise TypeError("show_icon must be a bool")
        self._show_window = show_window
        self._pause_tracking = pause_tracking
        self._resume_tracking = resume_tracking
        self._return_to_safe_mode = return_to_safe_mode
        self._quit_application = quit_application
        self._camera_status = CameraStatus.STOPPED
        self._live_input_state = LiveInputState.SAFE
        self._closed = False

        self._icon = QSystemTrayIcon(icon, self)
        self._icon.setObjectName("meyesSystemTrayIcon")
        self._icon.setToolTip("MEYES · SAFE MODE · Camera stopped")
        self._menu = QMenu()
        self._menu.setObjectName("meyesSystemTrayMenu")
        self._status_action = QAction("SAFE MODE · Camera stopped", self)
        self._status_action.setObjectName("trayStatusAction")
        self._status_action.setEnabled(False)
        self._show_action = QAction("Show MEYES", self)
        self._show_action.setObjectName("trayShowAction")
        self._tracking_action = QAction("Pause tracking", self)
        self._tracking_action.setObjectName("trayTrackingAction")
        self._safe_action = QAction("Return to Safe Mode", self)
        self._safe_action.setObjectName("traySafeModeAction")
        self._quit_action = QAction("Quit MEYES", self)
        self._quit_action.setObjectName("trayQuitAction")
        self._menu.addAction(self._status_action)
        self._menu.addSeparator()
        self._menu.addAction(self._show_action)
        self._menu.addAction(self._tracking_action)
        self._menu.addAction(self._safe_action)
        self._menu.addSeparator()
        self._menu.addAction(self._quit_action)
        self._icon.setContextMenu(self._menu)

        self._show_action.triggered.connect(self._show_window)
        self._tracking_action.triggered.connect(self._toggle_tracking)
        self._safe_action.triggered.connect(self._return_to_safe_mode)
        self._quit_action.triggered.connect(self._quit_application)
        self._icon.activated.connect(self._on_activated)
        self._render()
        if show_icon:
            self._icon.show()

    @property
    def icon(self) -> QSystemTrayIcon:
        """Expose the owned tray icon for platform composition and deterministic tests."""

        return self._icon

    def observe_camera_status(self, status: CameraStatus) -> None:
        if not isinstance(status, CameraStatus):
            raise TypeError("Expected CameraStatus")
        self._camera_status = status
        self._render()

    def observe_live_input_state(self, state: LiveInputState) -> None:
        if not isinstance(state, LiveInputState):
            raise TypeError("Expected LiveInputState")
        self._live_input_state = state
        self._render()

    @Slot()
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._icon.hide()
        for action in (
            self._show_action,
            self._tracking_action,
            self._safe_action,
            self._quit_action,
        ):
            action.setEnabled(False)

    @Slot()
    def _toggle_tracking(self) -> None:
        if self._camera_status is CameraStatus.RUNNING:
            self._pause_tracking()
        elif self._camera_status is CameraStatus.PAUSED:
            self._resume_tracking()

    @Slot(object)
    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self._show_window()

    def _render(self) -> None:
        input_labels = {
            LiveInputState.SAFE: "SAFE MODE",
            LiveInputState.ARMED: "LIVE INPUT",
            LiveInputState.FAULTED: "LIVE INPUT FAULT",
            LiveInputState.CLOSED: "LIVE INPUT CLOSED",
        }
        input_label = input_labels[self._live_input_state]
        camera_label = self._camera_status.value.replace("_", " ").capitalize()
        summary = f"{input_label} · Camera {camera_label.lower()}"
        self._status_action.setText(summary)
        self._icon.setToolTip(f"MEYES · {summary}")
        if self._camera_status is CameraStatus.RUNNING:
            self._tracking_action.setText("Pause tracking")
            self._tracking_action.setEnabled(not self._closed)
        elif self._camera_status is CameraStatus.PAUSED:
            self._tracking_action.setText("Resume tracking")
            self._tracking_action.setEnabled(not self._closed)
        else:
            self._tracking_action.setText("Tracking unavailable")
            self._tracking_action.setEnabled(False)
        self._safe_action.setEnabled(
            not self._closed
            and self._live_input_state in {LiveInputState.ARMED, LiveInputState.FAULTED}
        )
