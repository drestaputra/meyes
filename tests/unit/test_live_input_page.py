"""Live Input consent page tests with a fake Windows boundary."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QCoreApplication, QObject
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton
from pytestqt.qtbot import QtBot

from meyes.bindings.defaults import default_profile
from meyes.input.fake import FakeInputExecutor, InputCall
from meyes.input.windows_safety import WindowsEmergencyHotkey
from meyes.ui.live_input import LIVE_INPUT_CONSENT_PHRASE, LiveInputController, LiveInputState
from meyes.ui.live_input_page import LiveInputPage


@dataclass
class FakeSafetyApi:
    pressed: set[int] = field(default_factory=set)
    registrations: list[tuple[int, int, int, int]] = field(default_factory=list)
    unregistrations: list[tuple[int, int]] = field(default_factory=list)

    def register_hotkey(
        self,
        window_id: int,
        hotkey_id: int,
        modifiers: int,
        virtual_key: int,
    ) -> bool:
        self.registrations.append((window_id, hotkey_id, modifiers, virtual_key))
        return True

    def unregister_hotkey(self, window_id: int, hotkey_id: int) -> bool:
        self.unregistrations.append((window_id, hotkey_id))
        return True

    def key_is_down(self, virtual_key: int) -> bool:
        return virtual_key in self.pressed

    def hotkey_message_id(self, message: int) -> int | None:
        return message

    def last_error(self) -> int:
        return 0


def _page(
    qtbot: QtBot,
    *,
    safety: FakeSafetyApi | None = None,
    platform_supported: bool = True,
) -> tuple[LiveInputPage, LiveInputController, FakeInputExecutor, FakeSafetyApi]:
    executor = FakeInputExecutor()
    fake_safety = safety or FakeSafetyApi()

    def hotkey_factory(parent: QObject) -> WindowsEmergencyHotkey:
        application = QCoreApplication.instance()
        assert application is not None
        return WindowsEmergencyHotkey(
            api=fake_safety,
            application=application,
            parent=parent,
        )

    controller = LiveInputController(
        default_profile(),
        executor_factory=lambda: executor,
        hotkey_factory=hotkey_factory,
        platform_supported=platform_supported,
        clock=lambda: 2.0,
    )
    page = LiveInputPage(controller, lambda: 1234)
    controller.setParent(page)
    qtbot.addWidget(page)
    return page, controller, executor, fake_safety


def test_arm_requires_running_tracking_and_exact_phrase(qtbot: QtBot) -> None:
    page, controller, executor, safety = _page(qtbot)
    consent = page.findChild(QLineEdit, "liveInputConsent")
    arm = page.findChild(QPushButton, "armLiveInputButton")
    assert consent is not None and arm is not None

    consent.setText(LIVE_INPUT_CONSENT_PHRASE)
    assert not arm.isEnabled()
    page.set_tracking_available(True)
    assert arm.isEnabled()

    arm.click()

    assert controller.state is LiveInputState.ARMED
    assert consent.text() == ""
    assert len(safety.registrations) == 1
    assert executor.calls == [InputCall("release_all"), InputCall("release_all")]
    assert controller.disarm("test cleanup").success


def test_disarm_button_releases_and_restores_safe_status(qtbot: QtBot) -> None:
    page, controller, executor, safety = _page(qtbot)
    consent = page.findChild(QLineEdit, "liveInputConsent")
    arm = page.findChild(QPushButton, "armLiveInputButton")
    safe = page.findChild(QPushButton, "disarmLiveInputButton")
    status = page.findChild(QLabel, "liveInputStatus")
    assert consent is not None and arm is not None and safe is not None and status is not None
    page.set_tracking_available(True)
    consent.setText(LIVE_INPUT_CONSENT_PHRASE)
    arm.click()

    safe.click()

    assert controller.state is LiveInputState.SAFE
    assert "SAFE MODE" in status.text()
    assert len(safety.unregistrations) == 1
    assert executor.calls[-1] == InputCall("release_all")


def test_pressed_physical_input_fails_closed_with_visible_feedback(qtbot: QtBot) -> None:
    page, controller, executor, safety = _page(qtbot, safety=FakeSafetyApi(pressed={0x01}))
    consent = page.findChild(QLineEdit, "liveInputConsent")
    arm = page.findChild(QPushButton, "armLiveInputButton")
    feedback = page.findChild(QLabel, "liveInputFeedback")
    assert consent is not None and arm is not None and feedback is not None
    page.set_tracking_available(True)
    consent.setText(LIVE_INPUT_CONSENT_PHRASE)

    arm.click()

    assert controller.state is LiveInputState.SAFE
    assert "left mouse button" in feedback.text()
    assert len(safety.registrations) == 1
    assert len(safety.unregistrations) == 1
    assert executor.calls == []


def test_unsupported_platform_never_enables_arm(qtbot: QtBot) -> None:
    page, controller, executor, safety = _page(qtbot, platform_supported=False)
    consent = page.findChild(QLineEdit, "liveInputConsent")
    arm = page.findChild(QPushButton, "armLiveInputButton")
    status = page.findChild(QLabel, "liveInputStatus")
    assert consent is not None and arm is not None and status is not None
    page.set_tracking_available(True)
    consent.setText(LIVE_INPUT_CONSENT_PHRASE)

    assert not arm.isEnabled()
    assert "UNAVAILABLE" in status.text()
    assert controller.state is LiveInputState.SAFE
    assert safety.registrations == []
    assert executor.calls == []
