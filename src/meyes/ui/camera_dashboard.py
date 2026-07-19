"""Camera dashboard and lifecycle controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from meyes.camera.controller import CameraController, camera_device_list, camera_health
from meyes.camera.models import CameraHealth, CameraStatus


class CameraDashboard(QWidget):
    """Primary camera setup and health workspace."""

    def __init__(self, controller: CameraController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._image: QImage | None = None
        self._build_ui()
        self._connect_signals()
        self._apply_status(CameraHealth())
        self._controller.refresh_devices()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)

        title = QLabel("Camera dashboard")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Choose a camera and verify a stable local preview before enabling gesture tracking."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        camera_label = QLabel("Camera")
        self._camera_selector = QComboBox()
        self._camera_selector.setAccessibleName("Camera selector")
        self._camera_selector.setMinimumWidth(240)
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.setAccessibleName("Refresh camera list")
        self._mirror_checkbox = QCheckBox("Mirror preview")
        self._mirror_checkbox.setChecked(self._controller.settings.mirror)
        toolbar.addWidget(camera_label)
        toolbar.addWidget(self._camera_selector)
        toolbar.addWidget(self._refresh_button)
        toolbar.addSpacing(12)
        toolbar.addWidget(self._mirror_checkbox)
        toolbar.addStretch(1)

        body = QHBoxLayout()
        body.setSpacing(16)
        self._preview = QLabel("Searching for cameras…")
        self._preview.setObjectName("previewPlaceholder")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(480, 320)
        self._preview.setAccessibleName("Camera preview")
        body.addWidget(self._preview, stretch=3)
        body.addWidget(self._build_status_panel(), stretch=1)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self._start_button = QPushButton("Start camera")
        self._start_button.setObjectName("primaryButton")
        self._pause_button = QPushButton("Pause")
        self._resume_button = QPushButton("Resume")
        self._stop_button = QPushButton("Stop")
        controls.addWidget(self._start_button)
        controls.addWidget(self._pause_button)
        controls.addWidget(self._resume_button)
        controls.addWidget(self._stop_button)
        controls.addStretch(1)

        self._error_banner = QLabel()
        self._error_banner.setObjectName("errorBanner")
        self._error_banner.setWordWrap(True)
        self._error_banner.hide()

        root.addWidget(title)
        root.addWidget(description)
        root.addLayout(toolbar)
        root.addWidget(self._error_banner)
        root.addLayout(body, stretch=1)
        root.addLayout(controls)

    def _build_status_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(14)

        heading = QLabel("Camera status")
        heading.setObjectName("panelTitle")
        layout.addWidget(heading, 0, 0, 1, 2)

        self._status_value = self._add_status_row(layout, 1, "State")
        self._capture_fps_value = self._add_status_row(layout, 2, "Capture FPS")
        self._preview_fps_value = self._add_status_row(layout, 3, "Preview FPS")
        self._resolution_value = self._add_status_row(layout, 4, "Requested")
        self._safe_mode_value = self._add_status_row(layout, 5, "Input mode")
        self._resolution_value.setText(
            f"{self._controller.settings.width} x {self._controller.settings.height}"
        )
        self._safe_mode_value.setText("Safe mode")
        layout.setRowStretch(6, 1)
        return panel

    @staticmethod
    def _add_status_row(layout: QGridLayout, row: int, label: str) -> QLabel:
        name = QLabel(label)
        name.setObjectName("mutedText")
        value = QLabel("—")
        value.setObjectName("statusValue")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(name, row, 0)
        layout.addWidget(value, row, 1)
        return value

    def _connect_signals(self) -> None:
        self._controller.devices_changed.connect(self._on_devices_changed)
        self._controller.device_scan_changed.connect(self._on_scan_changed)
        self._controller.device_scan_failed.connect(self._on_error)
        self._controller.health_changed.connect(self._on_health_changed)
        self._controller.preview_changed.connect(self._on_preview_changed)
        self._controller.preview_fps_changed.connect(self._on_preview_fps_changed)
        self._camera_selector.currentIndexChanged.connect(self._on_camera_selected)
        self._refresh_button.clicked.connect(self._controller.refresh_devices)
        self._mirror_checkbox.toggled.connect(self._controller.set_mirror)
        self._start_button.clicked.connect(self._controller.start)
        self._pause_button.clicked.connect(self._controller.pause)
        self._resume_button.clicked.connect(self._controller.resume)
        self._stop_button.clicked.connect(self._controller.stop)

    @Slot(object)
    def _on_devices_changed(self, payload: object) -> None:
        devices = camera_device_list(payload)
        selected_index = self._controller.settings.camera_index
        self._camera_selector.blockSignals(True)
        self._camera_selector.clear()
        for device in devices:
            self._camera_selector.addItem(device.name, device.index)
        if not devices:
            self._camera_selector.addItem("No camera found", -1)
            self._preview.setText("No camera found\nConnect a camera, then choose Refresh.")
        else:
            selected_row = next(
                (row for row, device in enumerate(devices) if device.index == selected_index),
                0,
            )
            self._camera_selector.setCurrentIndex(selected_row)
            actual_index = devices[selected_row].index
            if actual_index != selected_index:
                self._controller.select_camera(actual_index)
            self._preview.setText("Camera ready to start")
        self._camera_selector.blockSignals(False)
        self._apply_status(CameraHealth())

    @Slot(bool)
    def _on_scan_changed(self, scanning: bool) -> None:
        self._refresh_button.setEnabled(
            not scanning and self._controller.status is CameraStatus.STOPPED
        )
        self._camera_selector.setEnabled(
            not scanning and self._controller.status is CameraStatus.STOPPED
        )
        if scanning:
            self._preview.setText("Searching for cameras…")

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self._error_banner.setText(message)
        self._error_banner.show()

    @Slot(object)
    def _on_health_changed(self, payload: object) -> None:
        health = camera_health(payload)
        self._apply_status(health)

    @Slot(QImage)
    def _on_preview_changed(self, image: QImage) -> None:
        self._image = image
        self._render_image()

    @Slot(float)
    def _on_preview_fps_changed(self, fps: float) -> None:
        self._preview_fps_value.setText(f"{fps:.1f}" if fps > 0 else "—")

    @Slot(int)
    def _on_camera_selected(self, row: int) -> None:
        data = self._camera_selector.itemData(row)
        if isinstance(data, int) and data >= 0:
            self._controller.select_camera(data)

    def _apply_status(self, health: CameraHealth) -> None:
        status = health.status
        self._status_value.setText(status.value.capitalize())
        self._status_value.setProperty("cameraStatus", status.value)
        self._status_value.style().unpolish(self._status_value)
        self._status_value.style().polish(self._status_value)
        self._capture_fps_value.setText(
            f"{health.measured_fps:.1f}" if health.measured_fps > 0 else "—"
        )
        if health.last_error:
            self._on_error(health.last_error)
        elif status in {CameraStatus.RUNNING, CameraStatus.PAUSED, CameraStatus.STOPPED}:
            self._error_banner.hide()

        has_camera = self._camera_selector.currentData() not in {None, -1}
        self._start_button.setEnabled(status is CameraStatus.STOPPED and has_camera)
        self._pause_button.setEnabled(status is CameraStatus.RUNNING)
        self._resume_button.setEnabled(status is CameraStatus.PAUSED)
        self._stop_button.setEnabled(
            status
            in {
                CameraStatus.STARTING,
                CameraStatus.RUNNING,
                CameraStatus.PAUSED,
                CameraStatus.RECOVERING,
                CameraStatus.ERROR,
            }
        )
        capture_active = status is not CameraStatus.STOPPED
        self._camera_selector.setEnabled(not capture_active)
        self._refresh_button.setEnabled(not capture_active)
        if status is CameraStatus.PAUSED:
            self._preview.setText("Camera paused")
        elif status is CameraStatus.STOPPED and self._image is not None:
            self._image = None
            self._preview.setPixmap(QPixmap())
            self._preview.setText("Camera stopped")

    def _render_image(self) -> None:
        if self._image is None:
            return
        pixmap = QPixmap.fromImage(self._image)
        scaled = pixmap.scaled(
            self._preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Preserve preview aspect ratio after window resizing."""
        super().resizeEvent(event)
        self._render_image()
