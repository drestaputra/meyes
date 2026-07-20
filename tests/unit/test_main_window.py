"""Application shell smoke tests."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import NoReturn

from PySide6.QtCore import QCoreApplication, QObject
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton
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
from meyes.calibration.persistence import AcceptedCalibrationRepository
from meyes.camera.models import CameraDevice, CameraHealth, CameraOptions, CameraStatus, FramePacket
from meyes.config.manager import ConfigManager
from meyes.config.models import AppConfig, CalibrationSettings
from meyes.cursor.screen_mapping import PhysicalScreenGeometry
from meyes.domain.actions import MouseButton, MouseDownAction
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import FaceObservation, HandObservation
from meyes.input.fake import FakeInputExecutor, InputCall
from meyes.input.windows_safety import WindowsEmergencyHotkey
from meyes.services.action_dispatcher import DispatcherState
from meyes.ui.calibration_controller import CalibrationFitOutcome, CalibrationFitState
from meyes.ui.calibration_persistence import CalibrationPersistenceStatus
from meyes.ui.cursor_diagnostics import CursorDiagnosticsStatus
from meyes.ui.live_input import LIVE_INPUT_CONSENT_PHRASE, LiveInputState
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
    def read(self) -> PhysicalScreenGeometry:
        return PhysicalScreenGeometry(0, 0, 1920, 1080)


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
    AcceptedCalibrationRepository(paths).save(accepted_calibration(), policy)

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

    assert window._calibration_persistence_result.status is CalibrationPersistenceStatus.RECOVERED
    assert window._cursor_diagnostics.snapshot.status is CursorDiagnosticsStatus.SUSPENDED
    assert window._live_input_controller.state is LiveInputState.SAFE
    assert persistence_label is not None
    assert "fake-only diagnostics" in persistence_label.text()
    assert paths.calibration_file.exists()


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
    assert "was saved" in persistence_label.text()


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
    consent.setText(LIVE_INPUT_CONSENT_PHRASE)
    window._calibration_controller.start()
    window._calibration_controller.begin_target()
    assert window._calibration_controller.snapshot.state.value == "collecting"

    arm.click()
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
