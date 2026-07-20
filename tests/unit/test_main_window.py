"""Application shell smoke tests."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import NoReturn

from pytestqt.qtbot import QtBot

from meyes.bindings.defaults import disabled_profile
from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.bindings.repository import BindingProfileRepository
from meyes.camera.models import CameraDevice, CameraOptions, FramePacket
from meyes.config.manager import ConfigManager
from meyes.config.models import AppConfig
from meyes.domain.actions import MouseButton, MouseDownAction
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import FaceObservation, HandObservation
from meyes.input.fake import InputCall
from meyes.services.action_dispatcher import DispatcherState
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
