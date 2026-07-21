"""Initial native application shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from meyes.bindings.manager import BindingManager
from meyes.bindings.models import BindingProfile
from meyes.bindings.repository import BindingProfileRepository
from meyes.calibration.persistence import (
    AcceptedCalibrationRepository,
    DeletedCalibrationBackup,
    DeletedCalibrationCatalog,
)
from meyes.camera.controller import CameraController
from meyes.camera.interface import CameraBackend
from meyes.camera.models import CameraHealth, CameraStatus
from meyes.config.manager import ConfigManager
from meyes.config.models import AppConfig, CameraSettings, CursorSettings
from meyes.cursor.screen_mapping import PhysicalScreenGeometryProvider
from meyes.cursor.windows_geometry import WindowsPrimaryScreenGeometryProvider
from meyes.input.windows_safety import EMERGENCY_HOTKEY_LABEL
from meyes.input.windows_sendinput import WindowsSendInputExecutor
from meyes.ui.action_simulation import ActionSimulationController
from meyes.ui.binding_editor_controller import BindingEditorController
from meyes.ui.bindings_page import BindingsPage
from meyes.ui.calibration_controller import (
    CalibrationController,
    calibration_fit_outcome,
)
from meyes.ui.calibration_page import CalibrationPage
from meyes.ui.calibration_persistence import (
    AcceptedCalibrationStore,
    CalibrationPersistenceLifecycle,
    CalibrationPersistenceResult,
    CalibrationPersistenceStatus,
)
from meyes.ui.camera_dashboard import CameraDashboard
from meyes.ui.camera_page import CameraPage, CameraSettingsSaveResult
from meyes.ui.cursor_diagnostics import CursorDiagnosticsController
from meyes.ui.cursor_provisioning import CursorPipelineProvisioner, CursorProvisioningStatus
from meyes.ui.diagnostics_page import DiagnosticsPage
from meyes.ui.first_run_wizard import FirstRunWizard
from meyes.ui.live_input import (
    EmergencyHotkeyFactory,
    InputExecutorFactory,
    LiveInputController,
    LiveInputSnapshot,
    LiveInputState,
)
from meyes.ui.live_input_page import LiveInputPage
from meyes.ui.placeholder_page import PlaceholderPage
from meyes.ui.privacy_page import PrivacyPage
from meyes.ui.profile_controller import ProfileController, binding_profile
from meyes.ui.profiles_page import ProfilesPage
from meyes.ui.sensitivity_page import SensitivityPage, SensitivitySaveResult
from meyes.ui.system_tray import SystemTrayController
from meyes.ui.theme import build_stylesheet
from meyes.ui.windows_accessibility import windows_high_contrast_enabled
from meyes.util.logging import get_logger
from meyes.util.paths import AppPaths
from meyes.vision.controller import VisionController
from meyes.vision.interface import FaceBackendFactory, HandBackendFactory

NAVIGATION_ITEMS = (
    "Dashboard",
    "Calibration",
    "Bindings",
    "Live Input",
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
        live_input_executor_factory: InputExecutorFactory | None = None,
        live_input_hotkey_factory: EmergencyHotkeyFactory | None = None,
        live_input_platform_supported: bool | None = None,
        cursor_geometry_provider: PhysicalScreenGeometryProvider | None = None,
        calibration_store: AcceptedCalibrationStore | None = None,
        high_contrast_enabled: bool | None = None,
    ) -> None:
        super().__init__()
        if high_contrast_enabled is not None and not isinstance(high_contrast_enabled, bool):
            raise TypeError("high_contrast_enabled must be a bool or None")
        self._config = config
        self._config_manager = config_manager
        self._camera_settings_pre_persisted = False
        self._first_run_wizard: FirstRunWizard | None = None
        self._system_tray: SystemTrayController | None = None
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
        self._binding_editor_controller = BindingEditorController(
            initial_profile,
            repository=profile_repository,
            parent=self,
        )
        self._calibration_controller = CalibrationController(
            acceptance_policy=config.calibration.acceptance_policy,
            parent=self,
        )
        self._cursor_diagnostics = CursorDiagnosticsController(
            parent=self,
            freshness_timeout=config.gestures.tracking_timeout_ms / 1000.0,
        )
        native_geometry = cursor_geometry_provider
        if native_geometry is None:
            try:
                native_geometry = WindowsPrimaryScreenGeometryProvider()
            except OSError:
                native_geometry = None
        self._cursor_pipeline_provisioner = CursorPipelineProvisioner(
            self._cursor_diagnostics,
            native_geometry,
            filter_settings=config.cursor.filter_settings,
            gate_settings=config.cursor.gate_settings,
        )
        executor_factory: InputExecutorFactory
        if live_input_executor_factory is None:

            def default_executor_factory() -> WindowsSendInputExecutor:
                return WindowsSendInputExecutor(
                    pointer_geometry_provider=self._cursor_pipeline_provisioner
                )

            executor_factory = default_executor_factory
        else:
            executor_factory = live_input_executor_factory
        self._live_input_controller = LiveInputController(
            initial_profile,
            executor_factory=executor_factory,
            hotkey_factory=live_input_hotkey_factory,
            platform_supported=live_input_platform_supported,
            parent=self,
        )
        persistence_store = calibration_store
        if persistence_store is None and config_manager is not None:
            persistence_store = AcceptedCalibrationRepository(config_manager.paths)
        self._calibration_persistence = CalibrationPersistenceLifecycle(
            self._cursor_pipeline_provisioner,
            persistence_store,
            config.calibration.acceptance_policy,
        )
        self._calibration_persistence_result = self._calibration_persistence.recover_once()
        self._vision_controller.gaze_feature_changed.connect(
            self._calibration_controller.observe_feature
        )
        self._vision_controller.gaze_feature_changed.connect(
            self._cursor_diagnostics.observe_feature
        )
        self._vision_controller.gaze_feature_cleared.connect(self._cursor_diagnostics.clear_feature)
        self._cursor_diagnostics.pointer_candidate.connect(self._live_input_controller.move_pointer)
        self._last_camera_status = CameraStatus.STOPPED
        self._camera_controller.settings_changed.connect(self._save_camera_settings)
        self._camera_controller.health_changed.connect(self._sync_vision_lifecycle)
        self._vision_controller.event_detected.connect(self._action_simulation.handle_event)
        self._vision_controller.event_detected.connect(self._live_input_controller.handle_event)
        self._vision_controller.event_detected.connect(self._cursor_diagnostics.handle_event)
        self._action_simulation.tracking_pause_requested.connect(
            self._camera_controller.pause,
            Qt.ConnectionType.QueuedConnection,
        )
        self._action_simulation.tracking_resume_requested.connect(
            self._camera_controller.resume,
            Qt.ConnectionType.QueuedConnection,
        )
        self._live_input_controller.tracking_pause_requested.connect(
            self._camera_controller.pause,
            Qt.ConnectionType.QueuedConnection,
        )
        self._live_input_controller.tracking_resume_requested.connect(
            self._camera_controller.resume,
            Qt.ConnectionType.QueuedConnection,
        )
        self._profile_controller.active_profile_changed.connect(self._on_active_profile_changed)
        self._profile_controller.active_profile_changed.connect(
            self._binding_editor_controller.observe_active_profile
        )
        self._binding_editor_controller.profile_saved.connect(self._on_binding_profile_saved)
        self.setWindowTitle("Meyes")
        self.resize(config.ui.window_width, config.ui.window_height)
        self.setMinimumSize(900, 640)
        use_system_theme = (
            windows_high_contrast_enabled()
            if high_contrast_enabled is None
            else high_contrast_enabled
        )
        self.setStyleSheet("" if use_system_theme else build_stylesheet())
        self.setCentralWidget(self._build_shell())
        self._calibration_controller.fit_changed.connect(self._sync_cursor_pipeline)
        self._calibration_page.set_persistence_result(self._calibration_persistence_result)
        if self._calibration_persistence_result.status is CalibrationPersistenceStatus.RECOVERED:
            self._logger.info("calibration_startup_recovered")
        elif (
            self._calibration_persistence_result.status is CalibrationPersistenceStatus.INCOMPATIBLE
        ):
            self._logger.warning("calibration_startup_display_mismatch")
        elif self._calibration_persistence_result.status is CalibrationPersistenceStatus.FAULTED:
            self._logger.error(
                "calibration_startup_recovery_failed",
                extra={
                    "quarantined": self._calibration_persistence_result.recovered_from is not None
                },
            )
        self._live_input_controller.snapshot_changed.connect(self._on_live_input_snapshot)
        self._on_live_input_snapshot(self._live_input_controller.snapshot)

    def _sync_cursor_pipeline(self, payload: object) -> None:
        calibration_fit_outcome(payload)
        result = self._calibration_persistence.replace(
            self._calibration_controller.accepted_calibration
        )
        self._calibration_persistence_result = result
        if hasattr(self, "_calibration_page"):
            self._calibration_page.set_persistence_result(result)
        if result.status is CalibrationPersistenceStatus.FAULTED:
            self._logger.error("calibration_persistence_lifecycle_failed")
        provisioning = result.provisioning
        if (
            self._calibration_controller.accepted_calibration is not None
            and provisioning is not None
            and provisioning.status is CursorProvisioningStatus.READY
            and self._last_camera_status is CameraStatus.RUNNING
        ):
            activation = self._live_input_page.request_arm(
                calibration_completed=True,
                dialog_parent=self._calibration_page.modal_parent,
            )
            if activation is not None and activation.success:
                self._logger.info("live_input_armed_after_calibration_confirmation")

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
        self._camera_status_label = QLabel("CAMERA STOPPED")
        self._camera_status_label.setObjectName("trackingStatus")
        self._camera_status_label.setAccessibleName("Camera tracking status")
        self._camera_command_button = QPushButton("Open Dashboard")
        self._camera_command_button.setObjectName("primaryButton")
        self._camera_command_button.clicked.connect(self._handle_camera_command)
        self._sync_top_bar_camera_status(CameraStatus.STOPPED)

        layout.addWidget(product)
        layout.addWidget(self._profile_label)
        layout.addStretch(1)
        layout.addWidget(self._camera_status_label)
        layout.addWidget(self._camera_command_button)
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
        navigation.setToolTip("Use arrow keys or Ctrl+1 through Ctrl+9 to change pages")
        self._navigation = navigation

        pages = QStackedWidget()
        pages.setObjectName("mainPages")
        self._camera_dashboard = CameraDashboard(self._camera_controller)
        self._calibration_page = CalibrationPage(
            self._calibration_controller,
            prepare_calibration=self._prepare_calibration,
            confirm_calibration_replace=self._confirm_calibration_replace,
            forget_calibration=self._forget_saved_calibration,
            backup_catalog=self._calibration_backup_catalog,
            restore_calibration=self._restore_saved_calibration,
            delete_calibration_backup=self._delete_saved_calibration_backup,
        )
        self._live_input_page = LiveInputPage(
            self._live_input_controller,
            lambda: int(self.winId()),
        )
        privacy_paths = self._config_manager.paths if self._config_manager else AppPaths.for_user()
        self._privacy_page = PrivacyPage(privacy_paths)
        self._sensitivity_page = SensitivityPage(
            self._config.cursor,
            self._save_cursor_settings,
        )
        self._camera_page = CameraPage(
            self._camera_controller,
            self._apply_camera_settings,
        )
        page_widgets: dict[str, QWidget] = {
            "Dashboard": self._camera_dashboard,
            "Calibration": self._calibration_page,
            "Bindings": BindingsPage(self._binding_editor_controller),
            "Live Input": self._live_input_page,
            "Sensitivity": self._sensitivity_page,
            "Camera": self._camera_page,
            "Diagnostics": DiagnosticsPage(
                self._vision_controller,
                action_simulation=self._action_simulation,
                cursor_diagnostics=self._cursor_diagnostics,
            ),
            "Profiles": ProfilesPage(
                self._profile_controller,
                prepare_transfer=self._prepare_profile_transfer,
            ),
            "Privacy": self._privacy_page,
        }
        for item in NAVIGATION_ITEMS:
            page = page_widgets.get(item) or PlaceholderPage(
                item,
                f"{item} is planned for a later implementation phase. "
                "The navigation entry is visible now so the product structure remains stable.",
            )
            pages.addWidget(page)
        pages.setCurrentIndex(selected_row)
        self._pages = pages
        navigation.currentRowChanged.connect(pages.setCurrentIndex)
        navigation.currentRowChanged.connect(self._on_navigation_changed)
        self._navigation_shortcuts: list[QShortcut] = []
        for row in range(len(NAVIGATION_ITEMS)):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{row + 1}"), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(lambda selected=row: self._select_navigation_row(selected))
            self._navigation_shortcuts.append(shortcut)
        layout.addWidget(navigation)
        layout.addWidget(pages, stretch=1)
        return workspace

    def _build_safety_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("safetyBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(24, 10, 24, 10)
        self._live_safety_status = QLabel("SAFE MODE · OS input disconnected")
        self._live_safety_status.setObjectName("liveSafetyStatus")
        shortcut = QLabel(f"Emergency: {EMERGENCY_HOTKEY_LABEL}")
        shortcut.setObjectName("mutedText")
        local = QLabel("Camera processing stays on this device")
        local.setObjectName("mutedText")
        layout.addWidget(self._live_safety_status)
        layout.addWidget(shortcut)
        layout.addStretch(1)
        layout.addWidget(local)
        return frame

    def _save_camera_settings(self, settings: object) -> None:
        if not isinstance(settings, CameraSettings):
            self._logger.error("invalid_camera_settings_signal")
            return
        if self._camera_settings_pre_persisted:
            return
        self._config = self._config.model_copy(update={"camera": settings})
        if self._config_manager is not None:
            self._config_manager.save(self._config)

    def _apply_camera_settings(self, settings: CameraSettings) -> CameraSettingsSaveResult:
        if not isinstance(settings, CameraSettings):
            raise TypeError("Expected CameraSettings")
        current = self._camera_controller.settings
        if self._camera_controller.status is not CameraStatus.STOPPED:
            return CameraSettingsSaveResult(
                False,
                "Stop camera capture before saving camera settings.",
                current,
            )
        disarmed = self._live_input_controller.disarm("camera settings change")
        if not disarmed.success:
            return CameraSettingsSaveResult(
                False,
                "Live Input could not be released; camera settings were not changed.",
                current,
            )
        candidate_settings = settings.model_copy(update={"camera_index": current.camera_index})
        candidate = self._config.model_copy(update={"camera": candidate_settings})
        if self._config_manager is not None:
            try:
                self._config_manager.save(candidate)
            except OSError:
                return CameraSettingsSaveResult(
                    False,
                    "Camera settings could not be saved; the prior values remain active.",
                    current,
                )
        self._config = candidate
        self._camera_settings_pre_persisted = True
        try:
            self._camera_controller.apply_settings(candidate_settings)
        finally:
            self._camera_settings_pre_persisted = False
        persisted = "saved" if self._config_manager is not None else "applied for this session"
        return CameraSettingsSaveResult(
            True,
            f"Camera settings {persisted}; they take effect on the next camera start.",
            candidate_settings,
        )

    def _save_cursor_settings(self, settings: CursorSettings) -> SensitivitySaveResult:
        if not isinstance(settings, CursorSettings):
            raise TypeError("Expected CursorSettings")
        disarmed = self._live_input_controller.disarm("cursor sensitivity change")
        if not disarmed.success:
            return SensitivitySaveResult(
                False,
                "Live Input could not be released; sensitivity settings were not changed.",
                self._config.cursor,
            )
        candidate = self._config.model_copy(update={"cursor": settings})
        if self._config_manager is not None:
            try:
                self._config_manager.save(candidate)
            except OSError:
                return SensitivitySaveResult(
                    False,
                    "Sensitivity settings could not be saved; the prior values remain active.",
                    self._config.cursor,
                )
        provisioning = self._cursor_pipeline_provisioner.update_settings(
            settings.filter_settings,
            settings.gate_settings,
        )
        self._config = candidate
        persisted = "saved" if self._config_manager is not None else "applied for this session"
        return SensitivitySaveResult(
            True,
            f"Sensitivity {persisted}. {provisioning.message}",
            settings,
            warning=provisioning.status is CursorProvisioningStatus.FAULTED,
        )

    def _persist_active_profile(self, profile_name: str) -> None:
        if self._config_manager is None:
            raise RuntimeError("Configuration persistence is unavailable")
        app_settings = self._config.app.model_copy(update={"active_profile": profile_name})
        candidate = self._config.model_copy(update={"app": app_settings})
        self._config_manager.save(candidate)
        self._config = candidate

    def _on_active_profile_changed(self, payload: object) -> None:
        profile = binding_profile(payload)
        result = self._live_input_controller.activate_profile(profile)
        if not result.success:
            self._logger.error(
                "live_profile_sync_failed",
                extra={"state": result.state.value},
            )
        self._set_profile_label(profile.profile_name)

    def _on_live_input_snapshot(self, payload: object) -> None:
        if not isinstance(payload, LiveInputSnapshot):
            self._logger.error("invalid_live_input_snapshot")
            return
        armed = payload.state is LiveInputState.ARMED
        labels = {
            LiveInputState.SAFE: "SAFE MODE · OS input disconnected",
            LiveInputState.ARMED: "LIVE INPUT · REAL OS OUTPUT ENABLED",
            LiveInputState.FAULTED: "LIVE INPUT FAULT · tracking paused",
            LiveInputState.CLOSED: "LIVE INPUT CLOSED",
        }
        self._live_safety_status.setText(labels[payload.state])
        self._live_safety_status.setProperty("liveInputState", payload.state.value)
        self._live_safety_status.style().unpolish(self._live_safety_status)
        self._live_safety_status.style().polish(self._live_safety_status)
        self._camera_dashboard.set_live_input_armed(armed)
        self._calibration_page.set_live_input_armed(armed)
        self._privacy_page.set_live_input_state(payload.state)
        if self._system_tray is not None:
            self._system_tray.observe_live_input_state(payload.state)

    def _on_binding_profile_saved(self, payload: object) -> None:
        binding_profile(payload)
        self._profile_controller.synchronize_catalog()

    def _prepare_profile_transfer(self) -> bool:
        result = self._live_input_controller.disarm("profile file dialog")
        if not result.success:
            self._logger.error(
                "profile_transfer_live_release_failed",
                extra={"state": result.state.value},
            )
        return result.success

    def _prepare_calibration(self) -> bool:
        result = self._live_input_controller.disarm("calibration collection")
        if not result.success:
            self._logger.error(
                "calibration_live_release_failed",
                extra={"state": result.state.value},
            )
        return result.success

    def _forget_saved_calibration(self) -> CalibrationPersistenceResult:
        result = self._calibration_persistence.forget()
        self._calibration_persistence_result = result
        if result.status is CalibrationPersistenceStatus.FAULTED:
            self._logger.error("calibration_forget_failed")
        elif result.status is CalibrationPersistenceStatus.FORGOTTEN:
            self._logger.info("calibration_forgotten")
        return result

    def _confirm_calibration_replace(self) -> CalibrationPersistenceResult:
        disarmed = self._live_input_controller.disarm("calibration replacement")
        if not disarmed.success:
            result = CalibrationPersistenceResult(
                CalibrationPersistenceStatus.PENDING_REPLACE,
                "Live Input could not be released; the prior saved calibration remains intact "
                "and replacement can be retried.",
            )
            self._calibration_persistence_result = result
            self._logger.error("calibration_replace_live_release_failed")
            return result
        result = self._calibration_persistence.replace(
            self._calibration_controller.accepted_calibration,
            confirm_existing=True,
        )
        self._calibration_persistence_result = result
        if result.status is CalibrationPersistenceStatus.SAVED:
            self._logger.info("calibration_replace_confirmed")
        elif result.status is CalibrationPersistenceStatus.FAULTED:
            self._logger.error("calibration_replace_failed")
        return result

    def _calibration_backup_catalog(self) -> DeletedCalibrationCatalog:
        return self._calibration_persistence.deleted_catalog()

    def _delete_saved_calibration_backup(
        self,
        backup: DeletedCalibrationBackup,
    ) -> CalibrationPersistenceResult:
        result = self._calibration_persistence.delete_backup(backup)
        self._calibration_persistence_result = result
        if result.status is CalibrationPersistenceStatus.DELETED:
            self._logger.info("calibration_backup_permanently_deleted")
        elif result.status is CalibrationPersistenceStatus.FAULTED:
            self._logger.error("calibration_backup_delete_failed")
        return result

    def _restore_saved_calibration(
        self,
        backup: DeletedCalibrationBackup,
    ) -> CalibrationPersistenceResult:
        result = self._calibration_persistence.restore(backup)
        self._calibration_persistence_result = result
        if result.status is CalibrationPersistenceStatus.RESTORED:
            self._logger.info("calibration_backup_restored")
        elif result.status is CalibrationPersistenceStatus.INCOMPATIBLE:
            self._logger.warning("calibration_backup_restore_display_mismatch")
        elif result.status is CalibrationPersistenceStatus.FAULTED:
            self._logger.error("calibration_backup_restore_failed")
        return result

    def _on_navigation_changed(self, row: int) -> None:
        if row < 0 or row >= len(NAVIGATION_ITEMS):
            return
        calibration_row = NAVIGATION_ITEMS.index("Calibration")
        self._calibration_page.set_page_active(row == calibration_row)
        selected_page = NAVIGATION_ITEMS[row]
        if selected_page == self._config.ui.selected_page:
            return
        ui_settings = self._config.ui.model_copy(update={"selected_page": selected_page})
        candidate = self._config.model_copy(update={"ui": ui_settings})
        if self._config_manager is not None:
            try:
                self._config_manager.save(candidate)
            except OSError:
                self._logger.error(
                    "navigation_preference_save_failed",
                    extra={"selected_page": selected_page},
                )
                return
        self._config = candidate

    def _select_navigation_row(self, row: int) -> None:
        if row < 0 or row >= len(NAVIGATION_ITEMS):
            raise ValueError("Navigation row is out of range")
        self._navigation.setCurrentRow(row)
        self._navigation.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _handle_camera_command(self) -> None:
        status = self._camera_controller.status
        if status is CameraStatus.RUNNING:
            self._camera_controller.pause()
        elif status is CameraStatus.PAUSED:
            self._camera_controller.resume()
        elif status in {CameraStatus.STOPPED, CameraStatus.ERROR}:
            self._select_navigation_row(NAVIGATION_ITEMS.index("Dashboard"))

    def _sync_top_bar_camera_status(self, status: CameraStatus) -> None:
        labels = {
            CameraStatus.STOPPED: "CAMERA STOPPED",
            CameraStatus.STARTING: "CAMERA STARTING",
            CameraStatus.RUNNING: "CAMERA RUNNING",
            CameraStatus.PAUSED: "CAMERA PAUSED",
            CameraStatus.RECOVERING: "CAMERA RECOVERING",
            CameraStatus.ERROR: "CAMERA ERROR",
            CameraStatus.STOPPING: "CAMERA STOPPING",
        }
        self._camera_status_label.setText(labels[status])
        self._camera_status_label.setProperty("cameraStatus", status.value)
        self._camera_status_label.style().unpolish(self._camera_status_label)
        self._camera_status_label.style().polish(self._camera_status_label)

        if status is CameraStatus.RUNNING:
            text = "Pause camera"
            tooltip = "Pause camera tracking and return Live Input to a released safe state"
            enabled = True
        elif status is CameraStatus.PAUSED:
            text = "Resume camera"
            tooltip = "Resume camera tracking; Live Input remains disconnected until re-armed"
            enabled = True
        elif status in {CameraStatus.STOPPED, CameraStatus.ERROR}:
            text = "Open Dashboard"
            tooltip = "Open Dashboard camera controls"
            enabled = True
        else:
            text = "Camera busy"
            tooltip = "Wait for the current camera transition to finish"
            enabled = False
        self._camera_command_button.setText(text)
        self._camera_command_button.setAccessibleName(text)
        self._camera_command_button.setToolTip(tooltip)
        self._camera_command_button.setEnabled(enabled)

    def _set_profile_label(self, profile_name: str) -> None:
        full_text = f"Profile: {profile_name}"
        display_text = self._profile_label.fontMetrics().elidedText(
            full_text,
            Qt.TextElideMode.ElideMiddle,
            220,
        )
        self._profile_label.setText(display_text)
        self._profile_label.setToolTip(full_text)

    def show_first_run_if_needed(self) -> FirstRunWizard | None:
        """Open one safe orientation dialog only when durable setup is still pending."""

        if (
            not self._config.app.first_run
            or self._config_manager is None
            or self._first_run_wizard is not None
        ):
            return self._first_run_wizard
        self._first_run_wizard = FirstRunWizard(self._complete_first_run, self)
        self._first_run_wizard.open()
        return self._first_run_wizard

    def _complete_first_run(self) -> bool:
        if self._config_manager is None:
            return False
        app_settings = self._config.app.model_copy(update={"first_run": False})
        candidate = self._config.model_copy(update={"app": app_settings})
        try:
            self._config_manager.save(candidate)
        except OSError:
            self._logger.error("first_run_completion_save_failed")
            return False
        self._config = candidate
        return True

    def _sync_vision_lifecycle(self, payload: object) -> None:
        if not isinstance(payload, CameraHealth):
            self._logger.error("invalid_camera_health_signal")
            return
        status = payload.status
        self._sync_top_bar_camera_status(status)
        if self._system_tray is not None:
            self._system_tray.observe_camera_status(status)
        self._live_input_page.set_tracking_available(status is CameraStatus.RUNNING)
        self._calibration_page.set_tracking_available(status is CameraStatus.RUNNING)
        if status is self._last_camera_status:
            return
        previous_status = self._last_camera_status
        self._last_camera_status = status
        if status is CameraStatus.RUNNING:
            self._action_simulation.start()
            self._cursor_diagnostics.start()
            self._vision_controller.start()
            self._show_calibration_onboarding_after_camera_start(previous_status)
        elif status in {CameraStatus.STOPPING, CameraStatus.STOPPED}:
            self._live_input_controller.disarm(f"camera:{status.value}")
            self._action_simulation.stop(f"camera:{status.value}")
            self._cursor_diagnostics.suspend()
            self._vision_controller.stop()
        else:
            self._live_input_controller.disarm(f"camera:{status.value}")
            self._action_simulation.pause(f"camera:{status.value}")
            self._cursor_diagnostics.suspend()
            self._vision_controller.suspend()

    def _show_calibration_onboarding_after_camera_start(
        self,
        previous_status: CameraStatus,
    ) -> None:
        if previous_status not in {CameraStatus.STOPPED, CameraStatus.STARTING}:
            return
        provisioning = self._calibration_persistence_result.provisioning
        if provisioning is not None and provisioning.status is CursorProvisioningStatus.READY:
            return
        self._select_navigation_row(NAVIGATION_ITEMS.index("Calibration"))
        self._calibration_page.show_camera_ready_onboarding()
        self._logger.info(
            "calibration_onboarding_opened_after_camera_start",
            extra={"calibration_status": self._calibration_persistence_result.status.value},
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop camera resources before allowing the window to close."""
        if self._system_tray is not None:
            self._system_tray.close()
        self._calibration_controller.cancel()
        self._live_input_controller.close()
        self._action_simulation.close()
        self._cursor_diagnostics.close()
        self._vision_controller.stop()
        self._camera_controller.shutdown()
        event.accept()

    def enable_system_tray(self) -> SystemTrayController | None:
        """Create one optional tray icon only when the desktop reports support."""

        if self._system_tray is not None or not QSystemTrayIcon.isSystemTrayAvailable():
            return self._system_tray
        icon = self.windowIcon()
        if icon.isNull():
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self._system_tray = SystemTrayController(
            icon,
            show_window=self._show_from_tray,
            pause_tracking=self._camera_controller.pause,
            resume_tracking=self._camera_controller.resume,
            return_to_safe_mode=lambda: self._live_input_controller.disarm("system tray"),
            quit_application=self.close,
            parent=self,
        )
        self._system_tray.observe_camera_status(self._camera_controller.status)
        self._system_tray.observe_live_input_state(self._live_input_controller.state)
        return self._system_tray

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
