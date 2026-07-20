"""Initial native application shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
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

from meyes.bindings.manager import BindingManager
from meyes.bindings.models import BindingProfile
from meyes.bindings.repository import BindingProfileRepository
from meyes.camera.controller import CameraController
from meyes.camera.interface import CameraBackend
from meyes.camera.models import CameraHealth, CameraStatus
from meyes.config.manager import ConfigManager
from meyes.config.models import AppConfig, CameraSettings
from meyes.ui.action_simulation import ActionSimulationController
from meyes.ui.camera_dashboard import CameraDashboard
from meyes.ui.diagnostics_page import DiagnosticsPage
from meyes.ui.placeholder_page import PlaceholderPage
from meyes.ui.profile_controller import ProfileController, binding_profile
from meyes.ui.profiles_page import ProfilesPage
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
        binding_profile: BindingProfile | None = None,
        profile_repository: BindingProfileRepository | None = None,
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
        initial_profile = (
            BindingManager(binding_profile).active_profile
            if binding_profile is not None
            else BindingManager().active_profile
        )
        self._action_simulation = ActionSimulationController(
            BindingManager(initial_profile),
            parent=self,
        )
        self._profile_controller = ProfileController(
            initial_profile,
            self._action_simulation,
            repository=profile_repository,
            persist_active_profile=(
                self._persist_active_profile if config_manager is not None else None
            ),
            parent=self,
        )
        self._last_camera_status = CameraStatus.STOPPED
        self._camera_controller.settings_changed.connect(self._save_camera_settings)
        self._camera_controller.health_changed.connect(self._sync_vision_lifecycle)
        self._vision_controller.event_detected.connect(self._action_simulation.handle_event)
        self._action_simulation.tracking_pause_requested.connect(
            self._camera_controller.pause,
            Qt.ConnectionType.QueuedConnection,
        )
        self._action_simulation.tracking_resume_requested.connect(
            self._camera_controller.resume,
            Qt.ConnectionType.QueuedConnection,
        )
        self._profile_controller.active_profile_changed.connect(self._on_active_profile_changed)
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
        self._profile_label = QLabel()
        self._profile_label.setObjectName("activeProfileLabel")
        self._profile_label.setAccessibleName("Active profile")
        self._profile_label.setMinimumWidth(0)
        self._profile_label.setMaximumWidth(240)
        self._set_profile_label(self._profile_controller.active_profile.profile_name)
        status = QLabel("TRACKING PAUSED")
        status.setObjectName("trackingStatus")
        resume = QPushButton("Resume tracking")
        resume.setObjectName("primaryButton")
        resume.setAccessibleName("Resume tracking")
        resume.setEnabled(False)
        resume.setToolTip("Camera controls will be available in Phase 1")

        layout.addWidget(product)
        layout.addWidget(self._profile_label)
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
            "Diagnostics": DiagnosticsPage(
                self._vision_controller,
                action_simulation=self._action_simulation,
            ),
            "Profiles": ProfilesPage(self._profile_controller),
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
        shortcut = QLabel("Emergency shortcut planned: Ctrl + Alt + F12")
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

    def _persist_active_profile(self, profile_name: str) -> None:
        if self._config_manager is None:
            raise RuntimeError("Configuration persistence is unavailable")
        app_settings = self._config.app.model_copy(update={"active_profile": profile_name})
        candidate = self._config.model_copy(update={"app": app_settings})
        self._config_manager.save(candidate)
        self._config = candidate

    def _on_active_profile_changed(self, payload: object) -> None:
        profile = binding_profile(payload)
        self._set_profile_label(profile.profile_name)

    def _set_profile_label(self, profile_name: str) -> None:
        full_text = f"Profile: {profile_name}"
        display_text = self._profile_label.fontMetrics().elidedText(
            full_text,
            Qt.TextElideMode.ElideMiddle,
            220,
        )
        self._profile_label.setText(display_text)
        self._profile_label.setToolTip(full_text)

    def _sync_vision_lifecycle(self, payload: object) -> None:
        if not isinstance(payload, CameraHealth):
            self._logger.error("invalid_camera_health_signal")
            return
        status = payload.status
        if status is self._last_camera_status:
            return
        self._last_camera_status = status
        if status is CameraStatus.RUNNING:
            self._action_simulation.start()
            self._vision_controller.start()
        elif status in {CameraStatus.STOPPING, CameraStatus.STOPPED}:
            self._action_simulation.stop(f"camera:{status.value}")
            self._vision_controller.stop()
        else:
            self._action_simulation.pause(f"camera:{status.value}")
            self._vision_controller.suspend()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop camera resources before allowing the window to close."""
        self._action_simulation.close()
        self._vision_controller.stop()
        self._camera_controller.shutdown()
        event.accept()
