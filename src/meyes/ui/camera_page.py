"""Dedicated validated camera capture settings and health view."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker, Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from meyes.camera.controller import CameraController, camera_health
from meyes.camera.models import CameraHealth, CameraStatus
from meyes.config.models import CameraSettings


@dataclass(frozen=True, slots=True)
class CameraSettingsSaveResult:
    """Composition-root result for one complete camera-settings save."""

    applied: bool
    message: str
    settings: CameraSettings


SaveCameraSettings = Callable[[CameraSettings], CameraSettingsSaveResult]


class CameraPage(QWidget):
    """Edit stopped-camera settings while exposing truthful capture health."""

    def __init__(
        self,
        controller: CameraController,
        save_settings: SaveCameraSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(controller, CameraController):
            raise TypeError("Expected CameraController")
        if not callable(save_settings):
            raise TypeError("save_settings must be callable")
        self._controller = controller
        self._save_settings = save_settings
        self._settings = controller.settings
        self._status = controller.status
        self.setObjectName("cameraPage")
        self._build_ui()
        self._connect_signals()
        self._render_settings(self._settings)
        self._render_health(CameraHealth(status=self._status))

    def _build_ui(self) -> None:
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("cameraPageScroll")
        scroll.viewport().setObjectName("cameraPageViewport")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("cameraPageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title = QLabel("Camera settings")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Configure the requested capture size, frame rate, and local preview mirroring. "
            "Camera selection, preview, and start/pause/resume controls remain on Dashboard."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        safety = QLabel(
            "CAPTURE SAFETY · Settings apply only while capture is stopped and saving releases "
            "Live Input first"
        )
        safety.setObjectName("safeBanner")
        safety.setWordWrap(True)
        self._feedback = QLabel()
        self._feedback.setObjectName("cameraSettingsFeedback")
        self._feedback.setWordWrap(True)
        self._feedback.hide()

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(safety)
        layout.addWidget(self._feedback)
        layout.addWidget(self._build_health_panel())
        layout.addWidget(self._build_settings_panel())

        self._dirty_status = QLabel("Saved settings · no pending changes")
        self._dirty_status.setObjectName("cameraSettingsDirtyStatus")
        self._dirty_status.setProperty("draftState", "clean")
        layout.addWidget(self._dirty_status)
        actions = QHBoxLayout()
        self._defaults_button = QPushButton("Stage defaults")
        self._defaults_button.setObjectName("cameraSettingsDefaultsButton")
        self._stop_button = QPushButton("Stop camera to edit")
        self._stop_button.setObjectName("cameraSettingsStopButton")
        self._stop_button.setProperty("dangerAction", True)
        self._save_button = QPushButton("Save camera settings")
        self._save_button.setObjectName("cameraSettingsSaveButton")
        self._save_button.setProperty("primaryAction", True)
        actions.addWidget(self._defaults_button)
        actions.addWidget(self._stop_button)
        actions.addStretch(1)
        actions.addWidget(self._save_button)
        layout.addLayout(actions)
        layout.addStretch(1)

        scroll.setWidget(content)
        page_layout.addWidget(scroll)

    def _build_health_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(10)
        heading = QLabel("Current capture health")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading, 0, 0, 1, 2)
        self._health_state = self._health_row(layout, 1, "State", "cameraSettingsHealthState")
        self._health_fps = self._health_row(layout, 2, "Measured FPS", "cameraSettingsHealthFps")
        self._health_failures = self._health_row(
            layout, 3, "Consecutive failures", "cameraSettingsHealthFailures"
        )
        self._health_message = QLabel()
        self._health_message.setObjectName("mutedText")
        self._health_message.setWordWrap(True)
        layout.addWidget(self._health_message, 4, 0, 1, 2)
        return panel

    @staticmethod
    def _health_row(layout: QGridLayout, row: int, name: str, object_name: str) -> QLabel:
        label = QLabel(name)
        label.setObjectName("mutedText")
        value = QLabel("—")
        value.setObjectName(object_name)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label, row, 0)
        layout.addWidget(value, row, 1)
        return value

    def _build_settings_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        heading = QLabel("Requested capture")
        heading.setObjectName("panelTitle")
        explanation = QLabel(
            "The camera driver may negotiate a different delivered rate or size. Dashboard reports "
            "measured FPS; these values are requests used on the next camera start."
        )
        explanation.setObjectName("mutedText")
        explanation.setWordWrap(True)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._width = QSpinBox()
        self._width.setObjectName("cameraWidthInput")
        self._width.setRange(320, 3840)
        self._width.setSuffix(" px")
        self._height = QSpinBox()
        self._height.setObjectName("cameraHeightInput")
        self._height.setRange(240, 2160)
        self._height.setSuffix(" px")
        self._target_fps = QSpinBox()
        self._target_fps.setObjectName("cameraTargetFpsInput")
        self._target_fps.setRange(1, 120)
        self._target_fps.setSuffix(" FPS")
        self._mirror = QCheckBox("Mirror preview only")
        self._mirror.setObjectName("cameraMirrorInput")
        self._mirror.setToolTip("Processing coordinates and landmarks are never mirrored here.")
        form.addRow("Width", self._width)
        form.addRow("Height", self._height)
        form.addRow("Target frame rate", self._target_fps)
        form.addRow("Preview", self._mirror)
        layout.addWidget(heading)
        layout.addWidget(explanation)
        layout.addLayout(form)
        return panel

    def _connect_signals(self) -> None:
        self._controller.health_changed.connect(self._on_health_changed)
        self._controller.settings_changed.connect(self._on_settings_changed)
        for field in (self._width, self._height, self._target_fps):
            field.valueChanged.connect(self._update_controls)
        self._mirror.stateChanged.connect(self._update_controls)
        self._defaults_button.clicked.connect(self._stage_defaults)
        self._stop_button.clicked.connect(self._controller.stop)
        self._save_button.clicked.connect(self._save)

    def _draft(self) -> CameraSettings:
        return CameraSettings(
            camera_index=self._settings.camera_index,
            width=self._width.value(),
            height=self._height.value(),
            target_fps=self._target_fps.value(),
            mirror=self._mirror.isChecked(),
        )

    def _render_settings(self, settings: CameraSettings) -> None:
        blockers = [
            QSignalBlocker(field)
            for field in (self._width, self._height, self._target_fps, self._mirror)
        ]
        self._width.setValue(settings.width)
        self._height.setValue(settings.height)
        self._target_fps.setValue(settings.target_fps)
        self._mirror.setChecked(settings.mirror)
        del blockers
        self._update_controls()

    def _render_health(self, health: CameraHealth) -> None:
        self._status = health.status
        self._health_state.setText(health.status.value.capitalize())
        self._health_state.setProperty("cameraStatus", health.status.value)
        self._health_fps.setText(f"{health.measured_fps:.1f}" if health.measured_fps > 0 else "—")
        self._health_failures.setText(str(health.failure_count))
        self._health_message.setText(health.last_error or health.message)
        self._update_controls()

    def _update_controls(self, *_args: object) -> None:
        dirty = self._draft() != self._settings
        stopped = self._status is CameraStatus.STOPPED
        self._save_button.setEnabled(dirty and stopped)
        self._stop_button.setVisible(not stopped)
        if dirty and not stopped:
            message = "Unsaved changes · stop camera before saving"
            state = "dirty"
        elif dirty:
            message = "Unsaved camera changes"
            state = "dirty"
        else:
            message = "Saved settings · no pending changes"
            state = "clean"
        self._dirty_status.setText(message)
        self._dirty_status.setProperty("draftState", state)
        self._dirty_status.style().unpolish(self._dirty_status)
        self._dirty_status.style().polish(self._dirty_status)

    @Slot(object)
    def _on_health_changed(self, payload: object) -> None:
        self._render_health(camera_health(payload))

    @Slot(object)
    def _on_settings_changed(self, payload: object) -> None:
        if not isinstance(payload, CameraSettings):
            raise TypeError("Expected CameraSettings")
        dirty = self._draft() != self._settings
        self._settings = payload
        if not dirty:
            self._render_settings(payload)
        else:
            self._update_controls()

    def _stage_defaults(self) -> None:
        defaults = CameraSettings(camera_index=self._settings.camera_index)
        self._render_settings(defaults)
        self._show_feedback("Defaults are staged. Stop capture, then save to apply.", "warning")

    def _save(self) -> None:
        result = self._save_settings(self._draft())
        if not isinstance(result, CameraSettingsSaveResult):
            raise TypeError("save_settings returned an invalid result")
        if result.applied:
            self._settings = result.settings
            self._render_settings(result.settings)
            self._show_feedback(result.message, "success")
        else:
            self._show_feedback(result.message, "error")

    def _show_feedback(self, message: str, status: str) -> None:
        self._feedback.setText(message)
        self._feedback.setProperty("feedbackStatus", status)
        self._feedback.style().unpolish(self._feedback)
        self._feedback.style().polish(self._feedback)
        self._feedback.show()
