"""Application shell smoke tests."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QStackedWidget,
)
from pytestqt.qtbot import QtBot

from meyes.bindings.defaults import disabled_profile
from meyes.bindings.editor import EditableActionKind
from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.bindings.repository import BindingProfileRepository
from meyes.calibration.acceptance import (
    AcceptedCalibration,
    CalibrationAcceptance,
    CalibrationAcceptanceState,
)
from meyes.calibration.mapper import (
    CalibrationFitResult,
    CalibrationValidation,
    PolynomialCalibrationMapper,
)
from meyes.calibration.persistence import AcceptedCalibrationRepository, CalibrationProvenance
from meyes.camera.models import CameraDevice, CameraHealth, CameraOptions, CameraStatus, FramePacket
from meyes.config.manager import ConfigManager
from meyes.config.models import AppConfig, CalibrationSettings
from meyes.cursor.screen_mapping import PhysicalScreenGeometry
from meyes.domain.actions import MouseButton, MouseDownAction
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import FaceObservation, HandObservation
from meyes.input.fake import FakeInputExecutor, InputCall
from meyes.input.windows_safety import WindowsEmergencyHotkey
from meyes.input.windows_sendinput import WindowsSendInputExecutor
from meyes.services.action_dispatcher import DispatcherState
from meyes.ui.calibration_controller import CalibrationFitOutcome, CalibrationFitState
from meyes.ui.calibration_page import (
    DELETE_CALIBRATION_BACKUP_PHRASE,
    FORGET_CALIBRATION_PHRASE,
    REPLACE_CALIBRATION_PHRASE,
    RESTORE_CALIBRATION_PHRASE,
)
from meyes.ui.calibration_persistence import CalibrationPersistenceStatus
from meyes.ui.cursor_diagnostics import CursorDiagnosticsStatus
from meyes.ui.first_run_wizard import FirstRunWizard
from meyes.ui.live_input import LIVE_INPUT_CONSENT_PHRASE, LiveInputResult, LiveInputState
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


class MainWindowSafetyApi:
    def __init__(self) -> None:
        self.registered = 0
        self.unregistered = 0

    def register_hotkey(
        self,
        window_id: int,
        hotkey_id: int,
        modifiers: int,
        virtual_key: int,
    ) -> bool:
        del window_id, hotkey_id, modifiers, virtual_key
        self.registered += 1
        return True

    def unregister_hotkey(self, window_id: int, hotkey_id: int) -> bool:
        del window_id, hotkey_id
        self.unregistered += 1
        return True

    def key_is_down(self, virtual_key: int) -> bool:
        del virtual_key
        return False

    def hotkey_message_id(self, message: int) -> int | None:
        return message

    def last_error(self) -> int:
        return 0


class FixedGeometryProvider:
    def __init__(self, geometry: PhysicalScreenGeometry | None = None) -> None:
        self.geometry = geometry or PhysicalScreenGeometry(0, 0, 1920, 1080)

    def read(self) -> PhysicalScreenGeometry:
        return self.geometry


def accepted_calibration() -> AcceptedCalibration:
    mapper = PolynomialCalibrationMapper(
        (0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    )
    fit = CalibrationFitResult(mapper, CalibrationValidation(18, 0.02, 0.015, 0.04))
    return AcceptedCalibration(
        fit,
        CalibrationAcceptance(CalibrationAcceptanceState.ACCEPTED),
    )


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


def test_high_contrast_mode_uses_system_theme_without_hiding_safety_text(qtbot: QtBot) -> None:
    window = MainWindow(
        AppConfig(),
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        high_contrast_enabled=True,
    )
    qtbot.addWidget(window)

    safety = window.findChild(QLabel, "liveSafetyStatus")
    navigation = window.findChild(QListWidget, "mainNavigation")
    assert window.styleSheet() == ""
    assert safety is not None and "SAFE MODE" in safety.text()
    assert navigation is not None and navigation.accessibleName() == "Main navigation"


def test_keyboard_navigation_switches_pages_and_persists_selection(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    config = AppConfig()
    manager.save(config)
    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        live_input_platform_supported=False,
    )
    qtbot.addWidget(window)
    window.show()
    navigation = window.findChild(QListWidget, "mainNavigation")
    pages = window.findChild(QStackedWidget, "mainPages")
    assert navigation is not None
    assert pages is not None
    navigation.setFocus()

    qtbot.keyClick(navigation, Qt.Key.Key_Down)  # type: ignore[no-untyped-call]

    assert navigation.currentRow() == 1
    assert pages.currentIndex() == 1
    assert manager.load().config.ui.selected_page == "Calibration"

    privacy_shortcut = next(
        shortcut
        for shortcut in window.findChildren(QShortcut)
        if shortcut.key() == QKeySequence("Ctrl+9")
    )
    privacy_shortcut.activated.emit()

    assert navigation.currentRow() == 8
    assert pages.currentIndex() == 8
    assert navigation.hasFocus()
    assert manager.load().config.ui.selected_page == "Privacy"


def test_first_run_completion_is_explicit_safe_and_persisted(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    config = AppConfig()
    manager.save(config)
    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        live_input_platform_supported=False,
    )
    qtbot.addWidget(window)

    wizard = window.show_first_run_if_needed()

    assert isinstance(wizard, FirstRunWizard)
    assert window._camera_controller.status is CameraStatus.STOPPED
    assert window._live_input_controller.state is LiveInputState.SAFE
    assert manager.load().config.app.first_run is True
    next_button = wizard.findChild(QPushButton, "firstRunNextButton")
    acknowledgement = wizard.findChild(QCheckBox, "firstRunSafetyAcknowledgement")
    finish = wizard.findChild(QPushButton, "firstRunFinishButton")
    assert next_button is not None
    assert acknowledgement is not None
    assert finish is not None
    next_button.click()
    next_button.click()
    acknowledgement.click()
    finish.click()

    assert manager.load().config.app.first_run is False
    assert window._camera_controller.status is CameraStatus.STOPPED
    assert window._live_input_controller.state is LiveInputState.SAFE


def test_sensitivity_save_persists_config_and_requests_live_release(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    config = AppConfig()
    manager.save(config)
    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        live_input_platform_supported=False,
    )
    qtbot.addWidget(window)
    minimum_cutoff = window.findChild(QDoubleSpinBox, "minimumCutoffInput")
    save_button = window.findChild(QPushButton, "sensitivitySaveButton")
    assert minimum_cutoff is not None
    assert save_button is not None

    with patch.object(
        window._live_input_controller,
        "disarm",
        wraps=window._live_input_controller.disarm,
    ) as disarm:
        minimum_cutoff.setValue(2.5)
        save_button.click()

    assert disarm.call_args.args == ("cursor sensitivity change",)
    assert manager.load().config.cursor.minimum_cutoff == 2.5
    assert window._cursor_pipeline_provisioner.filter_settings.minimum_cutoff == 2.5
    assert window._live_input_controller.state is LiveInputState.SAFE


def test_camera_settings_save_persists_and_updates_stopped_controller(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    config = AppConfig()
    manager.save(config)
    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        live_input_platform_supported=False,
    )
    qtbot.addWidget(window)
    width = window.findChild(QSpinBox, "cameraWidthInput")
    save_button = window.findChild(QPushButton, "cameraSettingsSaveButton")
    assert width is not None
    assert save_button is not None

    with patch.object(
        window._live_input_controller,
        "disarm",
        wraps=window._live_input_controller.disarm,
    ) as disarm:
        width.setValue(1280)
        save_button.click()

    assert disarm.call_args.args == ("camera settings change",)
    assert manager.load().config.camera.width == 1280
    assert window._camera_controller.settings.width == 1280
    assert window._live_input_controller.state is LiveInputState.SAFE


def test_default_live_executor_uses_provisioned_display_guard(qtbot: QtBot) -> None:
    window = MainWindow(
        AppConfig(),
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        cursor_geometry_provider=FixedGeometryProvider(),
    )
    qtbot.addWidget(window)

    executor = window._live_input_controller._executor_factory()

    assert isinstance(executor, WindowsSendInputExecutor)
    assert executor._pointer_geometry_provider is window._cursor_pipeline_provisioner
    window.close()


def test_startup_recovery_configures_only_fake_diagnostics_and_keeps_live_input_safe(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    calibration_settings = CalibrationSettings(
        maximum_root_mean_square_error=0.05,
        maximum_mean_error=0.04,
        maximum_error=0.1,
        minimum_holdout_samples=18,
    )
    config = AppConfig(calibration=calibration_settings)
    policy = calibration_settings.acceptance_policy
    assert policy is not None
    AcceptedCalibrationRepository(paths).save(
        accepted_calibration(),
        policy,
        CalibrationProvenance(
            datetime(2026, 7, 20, 8, 15, tzinfo=UTC),
            PhysicalScreenGeometry(0, 0, 1920, 1080),
        ),
    )

    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        cursor_geometry_provider=FixedGeometryProvider(),
        live_input_platform_supported=False,
    )
    qtbot.addWidget(window)
    persistence_label = window.findChild(QLabel, "calibrationPersistenceStatus")
    forget_confirmation = window.findChild(QLineEdit, "forgetCalibrationConfirmation")
    forget_button = window.findChild(QPushButton, "forgetCalibrationButton")
    backup_status = window.findChild(QLabel, "calibrationDeletedBackupStatus")
    restore_confirmation = window.findChild(QLineEdit, "restoreCalibrationConfirmation")
    restore_button = window.findChild(QPushButton, "restoreCalibrationButton")
    delete_backup_confirmation = window.findChild(QLineEdit, "deleteCalibrationBackupConfirmation")
    delete_backup_button = window.findChild(QPushButton, "deleteCalibrationBackupButton")
    recovered_result = window._calibration_persistence_result
    recovered_cursor = window._cursor_diagnostics.snapshot

    assert recovered_result.status is CalibrationPersistenceStatus.RECOVERED
    assert recovered_cursor.status is CursorDiagnosticsStatus.SUSPENDED
    assert window._live_input_controller.state is LiveInputState.SAFE
    assert persistence_label is not None
    assert "cursor pipeline" in persistence_label.text()
    assert paths.calibration_file.exists()
    assert forget_confirmation is not None
    assert forget_button is not None
    assert backup_status is not None
    assert restore_confirmation is not None
    assert restore_button is not None
    assert delete_backup_confirmation is not None
    assert delete_backup_button is not None

    forget_confirmation.setText(FORGET_CALIBRATION_PHRASE)
    assert forget_button.isEnabled()
    forget_button.click()
    forgotten_result = window._calibration_persistence_result
    forgotten_cursor = window._cursor_diagnostics.snapshot

    assert forgotten_result.status is CalibrationPersistenceStatus.FORGOTTEN
    assert forgotten_cursor.status is CursorDiagnosticsStatus.UNAVAILABLE
    assert window._live_input_controller.state is LiveInputState.SAFE
    assert not paths.calibration_file.exists()
    assert len(tuple(paths.data_dir.glob("accepted-calibration.deleted-*.json"))) == 1
    assert "recoverable deleted backup" in persistence_label.text()
    assert forget_confirmation.text() == ""
    assert "Newest deleted backup" in backup_status.text()

    restore_confirmation.setText(RESTORE_CALIBRATION_PHRASE)
    assert restore_button.isEnabled()
    restore_button.click()
    restored_result = window._calibration_persistence_result
    restored_cursor = window._cursor_diagnostics.snapshot

    assert restored_result.status is CalibrationPersistenceStatus.RESTORED
    assert restored_cursor.status is CursorDiagnosticsStatus.SUSPENDED
    assert window._live_input_controller.state is LiveInputState.SAFE
    assert paths.calibration_file.exists()
    assert len(tuple(paths.data_dir.glob("accepted-calibration.deleted-*.json"))) == 1
    assert "Restored calibration" in persistence_label.text()
    assert restore_confirmation.text() == ""

    delete_backup_confirmation.setText(DELETE_CALIBRATION_BACKUP_PHRASE)
    assert delete_backup_button.isEnabled()
    delete_backup_button.click()

    assert window._calibration_persistence_result.status is CalibrationPersistenceStatus.DELETED
    assert paths.calibration_file.exists()
    assert tuple(paths.data_dir.glob("accepted-calibration.deleted-*.json")) == ()
    assert "permanently removed" in persistence_label.text()
    assert delete_backup_confirmation.text() == ""


def test_newly_accepted_fit_is_saved_without_arming_live_input(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    calibration_settings = CalibrationSettings(
        maximum_root_mean_square_error=0.05,
        maximum_mean_error=0.04,
        maximum_error=0.1,
        minimum_holdout_samples=18,
    )
    config = AppConfig(calibration=calibration_settings)
    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        cursor_geometry_provider=FixedGeometryProvider(),
        live_input_platform_supported=False,
    )
    qtbot.addWidget(window)
    accepted = accepted_calibration()
    outcome = CalibrationFitOutcome(
        CalibrationFitState.READY,
        "accepted",
        accepted.fit_result.validation,
        accepted.acceptance,
    )
    window._calibration_controller._fit_result = accepted.fit_result
    window._calibration_controller._fit_outcome = outcome

    window._calibration_controller.fit_changed.emit(outcome)

    policy = calibration_settings.acceptance_policy
    assert policy is not None
    loaded = AcceptedCalibrationRepository(paths).load(policy)
    persistence_label = window.findChild(QLabel, "calibrationPersistenceStatus")
    assert loaded.calibration == accepted
    assert window._calibration_persistence_result.status is CalibrationPersistenceStatus.SAVED
    assert window._live_input_controller.state is LiveInputState.SAFE
    assert persistence_label is not None
    assert "Saved calibration" in persistence_label.text()


def test_existing_calibration_is_replaced_only_after_exact_confirmation(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    calibration_settings = CalibrationSettings(
        maximum_root_mean_square_error=0.05,
        maximum_mean_error=0.04,
        maximum_error=0.1,
        minimum_holdout_samples=18,
    )
    config = AppConfig(calibration=calibration_settings)
    policy = calibration_settings.acceptance_policy
    assert policy is not None
    original = accepted_calibration()
    AcceptedCalibrationRepository(paths).save(
        original,
        policy,
        CalibrationProvenance(
            datetime(2026, 7, 20, 8, 15, tzinfo=UTC),
            PhysicalScreenGeometry(0, 0, 1920, 1080),
        ),
    )
    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        cursor_geometry_provider=FixedGeometryProvider(),
        live_input_platform_supported=False,
    )
    qtbot.addWidget(window)
    replacement = AcceptedCalibration(
        CalibrationFitResult(
            PolynomialCalibrationMapper(
                (0.02, 0.98, 0.0, 0.0, 0.0, 0.0),
                (0.01, 0.0, 0.99, 0.0, 0.0, 0.0),
            ),
            original.fit_result.validation,
        ),
        original.acceptance,
    )
    outcome = CalibrationFitOutcome(
        CalibrationFitState.READY,
        "accepted replacement",
        replacement.fit_result.validation,
        replacement.acceptance,
    )
    window._calibration_controller._fit_result = replacement.fit_result
    window._calibration_controller._fit_outcome = outcome

    window._calibration_controller.fit_changed.emit(outcome)

    repository = AcceptedCalibrationRepository(paths)
    confirmation = window.findChild(QLineEdit, "replaceCalibrationConfirmation")
    button = window.findChild(QPushButton, "replaceCalibrationButton")
    pending_result = window._calibration_persistence_result
    assert pending_result.status is CalibrationPersistenceStatus.PENDING_REPLACE
    assert repository.load(policy).calibration == original
    assert confirmation is not None and button is not None
    confirmation.setText(REPLACE_CALIBRATION_PHRASE)
    assert button.isEnabled()

    with patch.object(
        window._live_input_controller,
        "disarm",
        return_value=LiveInputResult(False, LiveInputState.FAULTED, "release failed"),
    ):
        button.click()

    failed_result = window._calibration_persistence_result
    assert failed_result.status is CalibrationPersistenceStatus.PENDING_REPLACE
    assert repository.load(policy).calibration == original
    assert confirmation.text() == ""
    confirmation.setText(REPLACE_CALIBRATION_PHRASE)
    assert button.isEnabled()

    button.click()

    assert window._calibration_persistence_result.status is CalibrationPersistenceStatus.SAVED
    assert repository.load(policy).calibration == replacement
    assert confirmation.text() == ""
    assert not button.isEnabled()
    assert window._live_input_controller.state is LiveInputState.SAFE


def test_startup_recovery_rejects_changed_primary_display_geometry(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    calibration_settings = CalibrationSettings(
        maximum_root_mean_square_error=0.05,
        maximum_mean_error=0.04,
        maximum_error=0.1,
        minimum_holdout_samples=18,
    )
    config = AppConfig(calibration=calibration_settings)
    policy = calibration_settings.acceptance_policy
    assert policy is not None
    AcceptedCalibrationRepository(paths).save(
        accepted_calibration(),
        policy,
        CalibrationProvenance(
            datetime(2026, 7, 20, 8, 15, tzinfo=UTC),
            PhysicalScreenGeometry(0, 0, 1920, 1080),
        ),
    )

    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        cursor_geometry_provider=FixedGeometryProvider(PhysicalScreenGeometry(0, 0, 2560, 1440)),
        live_input_platform_supported=False,
    )
    qtbot.addWidget(window)
    persistence_label = window.findChild(QLabel, "calibrationPersistenceStatus")

    assert (
        window._calibration_persistence_result.status is CalibrationPersistenceStatus.INCOMPATIBLE
    )
    assert window._cursor_diagnostics.snapshot.status is CursorDiagnosticsStatus.UNAVAILABLE
    assert window._live_input_controller.state is LiveInputState.SAFE
    assert persistence_label is not None
    assert "differs" in persistence_label.text()


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
    assert window._action_simulation.state is DispatcherState.CLOSED
    assert not [
        thread.name
        for thread in threading.enumerate()
        if thread.name in {"meyes-face", "meyes-hand"}
    ]


def test_window_wires_fake_dispatch_and_releases_before_close(qtbot: QtBot) -> None:
    bindings = dict(disabled_profile("Close safety").bindings)
    bindings[BindableGesture.LEFT_TEMPLE_HOLD] = MouseDownAction(button=MouseButton.LEFT)
    profile = BindingProfile(profile_name="Close safety", bindings=bindings)
    window = MainWindow(
        AppConfig(),
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        binding_profile=profile,
    )
    qtbot.addWidget(window)
    assert window._action_simulation.snapshot.profile_name == "Close safety"
    assert window._action_simulation.start().success is True
    timestamp = time.monotonic()

    window._vision_controller.event_detected.emit(
        GestureEvent(
            GestureEventType.LEFT_TEMPLE_HOLD_START,
            timestamp=timestamp,
            source_sequence=1,
            duration_ms=550.0,
        )
    )

    assert InputCall("mouse_down", (MouseButton.LEFT,)) in window._action_simulation.simulated_calls

    window.close()

    assert window._action_simulation.state is DispatcherState.CLOSED
    assert window._action_simulation.simulated_calls[-2:] == (
        InputCall("mouse_up", (MouseButton.LEFT,)),
        InputCall("release_all"),
    )


def test_window_wires_explicit_live_input_and_camera_pause_disarms(qtbot: QtBot) -> None:
    executor = FakeInputExecutor()
    safety = MainWindowSafetyApi()

    def hotkey_factory(parent: QObject) -> WindowsEmergencyHotkey:
        application = QCoreApplication.instance()
        assert application is not None
        return WindowsEmergencyHotkey(api=safety, application=application, parent=parent)

    window = MainWindow(
        AppConfig(),
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        live_input_executor_factory=lambda: executor,
        live_input_hotkey_factory=hotkey_factory,
        live_input_platform_supported=True,
    )
    qtbot.addWidget(window)
    window.show()
    window._live_input_page.set_tracking_available(True)
    consent = window.findChild(QLineEdit, "liveInputConsent")
    arm = window.findChild(QPushButton, "armLiveInputButton")
    safety_status = window.findChild(QLabel, "liveSafetyStatus")
    assert consent is not None and arm is not None and safety_status is not None
    window._cursor_diagnostics.pointer_candidate.emit(111, 222)
    assert InputCall("move_pointer", (111, 222)) not in executor.calls
    consent.setText(LIVE_INPUT_CONSENT_PHRASE)
    window._calibration_controller.start()
    window._calibration_controller.begin_target()
    assert window._calibration_controller.snapshot.state.value == "collecting"

    arm.click()
    window._cursor_diagnostics.pointer_candidate.emit(111, 222)
    timestamp = time.monotonic()
    window._vision_controller.event_detected.emit(
        GestureEvent(
            GestureEventType.LEFT_WINK,
            timestamp=timestamp,
            source_sequence=1,
            duration_ms=180.0,
        )
    )

    assert window._live_input_controller.state is LiveInputState.ARMED
    assert safety.registered == 1
    assert window._calibration_controller.snapshot.state.value == "cancelled"
    assert InputCall("move_pointer", (111, 222)) in executor.calls
    assert InputCall("mouse_click", (MouseButton.LEFT,)) in executor.calls
    assert "LIVE INPUT" in safety_status.text()

    assert window._prepare_profile_transfer()
    transfer_snapshot = window._live_input_controller.snapshot
    assert transfer_snapshot.state.value == "safe"
    assert safety.unregistered == 1
    consent.setText(LIVE_INPUT_CONSENT_PHRASE)
    arm.click()
    rearmed_snapshot = window._live_input_controller.snapshot
    assert rearmed_snapshot.state.value == "armed"
    assert safety.registered == 2

    assert window._prepare_calibration()
    calibration_snapshot = window._live_input_controller.snapshot
    assert calibration_snapshot.state.value == "safe"
    assert safety.unregistered == 2
    consent.setText(LIVE_INPUT_CONSENT_PHRASE)
    arm.click()
    assert window._live_input_controller.snapshot.state.value == "armed"
    assert safety.registered == 3

    window._sync_vision_lifecycle(
        CameraHealth(status=CameraStatus.PAUSED, message="Camera is paused")
    )

    paused_snapshot = window._live_input_controller.snapshot
    assert paused_snapshot.state.value == "safe"
    assert safety.unregistered == 3
    assert executor.calls[-1] == InputCall("release_all")
    assert "SAFE MODE" in safety_status.text()

    window.close()
    closed_snapshot = window._live_input_controller.snapshot
    assert closed_snapshot.state.value == "closed"


def test_camera_running_keeps_live_input_safe_until_explicit_consent(qtbot: QtBot) -> None:
    executor = FakeInputExecutor()
    safety = MainWindowSafetyApi()

    def hotkey_factory(parent: QObject) -> WindowsEmergencyHotkey:
        application = QCoreApplication.instance()
        assert application is not None
        return WindowsEmergencyHotkey(api=safety, application=application, parent=parent)

    window = MainWindow(
        AppConfig(),
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        live_input_executor_factory=lambda: executor,
        live_input_hotkey_factory=hotkey_factory,
        live_input_platform_supported=True,
    )
    qtbot.addWidget(window)
    window.show()

    window._sync_vision_lifecycle(
        CameraHealth(status=CameraStatus.RUNNING, message="Camera is running")
    )

    safety_status = window.findChild(QLabel, "liveSafetyStatus")
    assert window._live_input_controller.state is LiveInputState.SAFE
    assert safety.registered == 0
    assert executor.calls == []
    assert safety_status is not None and "SAFE MODE" in safety_status.text()

    window.close()
    assert safety.unregistered == 0


def test_profile_activation_updates_runtime_config_and_top_bar(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    config = AppConfig()
    manager.save(config)
    repository = BindingProfileRepository(paths)
    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        binding_profile=repository.load("Default").profile,
        profile_repository=repository,
    )
    qtbot.addWidget(window)

    created = window._profile_controller.create_disabled(" Work ")
    activated = window._profile_controller.activate("work")

    assert created.success and created.profile_name == "Work"
    assert activated.success and activated.profile_name == "Work"
    assert manager.load().config.app.active_profile == "Work"
    assert window._config.app.active_profile == "Work"
    assert window._profile_label.text() == "Profile: Work"
    assert window._profile_label.toolTip() == "Profile: Work"
    assert window._action_simulation.snapshot.profile_name == "Work"
    assert window._action_simulation.state is DispatcherState.PAUSED
    assert window._live_input_controller.snapshot.profile_name == "Work"
    assert window._live_input_controller.state is LiveInputState.SAFE


def test_maximum_length_profile_name_is_elided_without_expanding_shell(
    qtbot: QtBot,
) -> None:
    profile_name = "W" * 80
    window = MainWindow(
        AppConfig(),
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        binding_profile=disabled_profile(profile_name),
    )
    qtbot.addWidget(window)
    window.resize(900, 640)
    window.show()

    assert "…" in window._profile_label.text()
    assert window._profile_label.toolTip() == f"Profile: {profile_name}"
    assert window._profile_label.sizeHint().width() <= 240
    assert window._profile_label.width() <= 240
    assert window.minimumSizeHint().width() <= 1000
    assert window.width() == 900


def test_binding_draft_save_updates_catalog_without_runtime_activation(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    config = AppConfig()
    manager.save(config)
    repository = BindingProfileRepository(paths)
    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        binding_profile=repository.load("Default").profile,
        profile_repository=repository,
    )
    qtbot.addWidget(window)

    edited = window._binding_editor_controller.edit_binding(
        BindableGesture.LEFT_WINK,
        EditableActionKind.DISABLED,
        "",
    )
    saved = window._binding_editor_controller.save_as_copy("Quiet Copy")

    assert edited.success
    assert saved.success and saved.profile_name == "Quiet Copy"
    assert window._profile_controller.profile_names == ("Default", "Quiet Copy")
    assert window._profile_controller.active_profile.profile_name == "Default"
    assert window._action_simulation.active_profile.profile_name == "Default"
    assert window._action_simulation.state is DispatcherState.PAUSED
    assert window._config.app.active_profile == "Default"
    assert manager.load().config.app.active_profile == "Default"
    assert window._binding_editor_controller.state.source_profile.profile_name == "Quiet Copy"
    assert window._binding_editor_controller.state.active_profile_name == "Default"


def test_inactive_profile_lifecycle_does_not_change_runtime_or_config(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    manager = ConfigManager(paths)
    config = AppConfig()
    manager.save(config)
    repository = BindingProfileRepository(paths)
    window = MainWindow(
        config,
        camera_backend=EmptyBackend(),
        face_backend_factory=EmptyFaceBackend,
        hand_backend_factory=EmptyHandBackend,
        config_manager=manager,
        binding_profile=repository.load("Default").profile,
        profile_repository=repository,
    )
    qtbot.addWidget(window)
    snapshot_before = window._action_simulation.snapshot

    created = window._profile_controller.create_disabled("Work")
    renamed = window._profile_controller.rename("Work", "Focus")
    restored = window._profile_controller.restore_default("Focus", confirmed=True)
    deleted = window._profile_controller.delete("Focus", "Focus")

    assert created.success
    assert renamed.success and renamed.profile_name == "Focus"
    assert restored.success and restored.profile_name == "Focus"
    assert deleted.success
    assert window._profile_controller.profile_names == ("Default",)
    assert window._profile_controller.active_profile.profile_name == "Default"
    assert window._action_simulation.snapshot == snapshot_before
    assert window._config.app.active_profile == "Default"
    assert manager.load().config.app.active_profile == "Default"
    assert window._binding_editor_controller.state.active_profile_name == "Default"
    assert not (paths.profiles_dir / "Focus.json").exists()
    assert len(tuple(paths.profiles_dir.glob("Focus.deleted-*.bak"))) == 1
