"""Initial native application shell."""

from __future__ import annotations

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from meyes.camera.controller import CameraController
from meyes.camera.interface import CameraBackend
from meyes.camera.models import CameraHealth, CameraStatus
from meyes.config.manager import ConfigManager
from meyes.config.models import AppConfig, CameraSettings
from meyes.ui.camera_dashboard import CameraDashboard
from meyes.ui.diagnostics_page import DiagnosticsPage
from meyes.ui.placeholder_page import PlaceholderPage
from meyes.ui.theme import build_stylesheet
from meyes.util.logging import get_logger
from meyes.vision.controller import VisionController
from meyes.vision.interface import FaceBackendFactory, HandBackendFactory

NAVIGATION_ITEMS = (
    "Dashboard",
    "Calibration",
    "Bindings",
    "Sensitivity",
    "Camera",
    "Profiles",
    "Diagnostics",
    "Privacy",
)


class MainWindow(QMainWindow):
    """MEYES control-room shell with persistent safety status."""

    def __init__(
        self,
        config: AppConfig,
        camera_backend: CameraBackend,
        face_backend_factory: FaceBackendFactory,
        hand_backend_factory: HandBackendFactory,
        config_manager: ConfigManager | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._config_manager = config_manager
        self._logger = get_logger("APP")
        self._camera_controller = CameraController(camera_backend, config.camera, parent=self)
        self._vision_controller = VisionController(
            self._camera_controller.frame_buffer,
            face_backend_factory,
            config.gestures,
            parent=self,
            hand_backend_factory=hand_backend_factory,
        )
        self._last_camera_status = CameraStatus.STOPPED
        self._camera_controller.settings_changed.connect(self._save_camera_settings)
        self._camera_controller.health_changed.connect(self._sync_vision_lifecycle)
        self.setWindowTitle("Meyes")
        self.resize(config.ui.window_width, config.ui.window_height)
        self.setMinimumSize(900, 640)
        self.setStyleSheet(build_stylesheet())
        self.setCentralWidget(self._build_shell())

    def _build_shell(self) -> QWidget:
        root = QWidget(self)
        root.setObjectName("appRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_top_bar())
        layout.addWidget(self._build_workspace(), stretch=1)
        layout.addWidget(self._build_safety_bar())
        return root

    def _build_top_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("topBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(20)

        product = QLabel("MEYES")
        product.setObjectName("productName")
        profile = QLabel(f"Profile: {self._config.app.active_profile}")
        profile.setObjectName("mutedText")
        status = QLabel("TRACKING PAUSED")
        status.setObjectName("trackingStatus")
        resume = QPushButton("Resume tracking")
        resume.setObjectName("primaryButton")
        resume.setAccessibleName("Resume tracking")
        resume.setEnabled(False)
        resume.setToolTip("Camera controls will be available in Phase 1")

        layout.addWidget(product)
        layout.addWidget(profile)
        layout.addStretch(1)
        layout.addWidget(status)
        layout.addWidget(resume)
        return frame

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        workspace.setObjectName("workspace")
        layout = QHBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        navigation = QListWidget()
        navigation.setObjectName("mainNavigation")
        navigation.setFixedWidth(210)
        navigation.addItems(NAVIGATION_ITEMS)
        selected_row = max(0, NAVIGATION_ITEMS.index(self._config.ui.selected_page))
        navigation.setCurrentRow(selected_row)
        navigation.setAccessibleName("Main navigation")

        pages = QStackedWidget()
        pages.setObjectName("mainPages")
        page_widgets: dict[str, QWidget] = {
            "Dashboard": CameraDashboard(self._camera_controller),
            "Diagnostics": DiagnosticsPage(self._vision_controller),
        }
        for item in NAVIGATION_ITEMS:
            page = page_widgets.get(item) or PlaceholderPage(
                item,
                f"{item} is planned for a later implementation phase. "
                "The navigation entry is visible now so the product structure remains stable.",
            )
            pages.addWidget(page)
        pages.setCurrentIndex(selected_row)
        navigation.currentRowChanged.connect(pages.setCurrentIndex)
        layout.addWidget(navigation)
        layout.addWidget(pages, stretch=1)
        return workspace

    def _build_safety_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("safetyBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(24, 10, 24, 10)
        shortcut = QLabel("Ctrl + Alt + F12 pauses tracking immediately")
        local = QLabel("Camera processing stays on this device")
        local.setObjectName("mutedText")
        layout.addWidget(shortcut)
        layout.addStretch(1)
        layout.addWidget(local)
        return frame

    def _save_camera_settings(self, settings: object) -> None:
        if not isinstance(settings, CameraSettings):
            self._logger.error("invalid_camera_settings_signal")
            return
        self._config = self._config.model_copy(update={"camera": settings})
        if self._config_manager is not None:
            self._config_manager.save(self._config)

    def _sync_vision_lifecycle(self, payload: object) -> None:
        if not isinstance(payload, CameraHealth):
            self._logger.error("invalid_camera_health_signal")
            return
        status = payload.status
        if status is self._last_camera_status:
            return
        self._last_camera_status = status
        if status is CameraStatus.RUNNING:
            self._vision_controller.start()
        elif status in {CameraStatus.STOPPING, CameraStatus.STOPPED}:
            self._vision_controller.stop()
        else:
            self._vision_controller.suspend()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop camera resources before allowing the window to close."""
        self._vision_controller.stop()
        self._camera_controller.shutdown()
        event.accept()
