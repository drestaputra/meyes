"""Explicit-consent live-input controller tests using only fake native boundaries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtCore import QCoreApplication, QObject
from pytestqt.qtbot import QtBot

from meyes.bindings.defaults import default_profile, disabled_profile
from meyes.domain.actions import MouseButton
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.input.fake import FakeInputExecutor, InputCall
from meyes.input.windows_safety import WindowsEmergencyHotkey
from meyes.ui.live_input import LiveInputController, LiveInputState


@dataclass
class FakeSafetyApi:
    pressed: set[int] = field(default_factory=set)
    register_result: bool = True
    unregister_result: bool = True
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
        return self.register_result

    def unregister_hotkey(self, window_id: int, hotkey_id: int) -> bool:
        self.unregistrations.append((window_id, hotkey_id))
        return self.unregister_result

    def key_is_down(self, virtual_key: int) -> bool:
        return virtual_key in self.pressed

    def hotkey_message_id(self, message: int) -> int | None:
        return message

    def last_error(self) -> int:
        return 5


class FailReleaseExecutor(FakeInputExecutor):
    def release_all(self) -> None:
        super().release_all()
        raise RuntimeError("release unavailable")


class FailThirdReleaseExecutor(FakeInputExecutor):
    def release_all(self) -> None:
        super().release_all()
        if self.release_all_calls == 3:
            raise RuntimeError("one-shot profile transition failure")


class FailMoveExecutor(FakeInputExecutor):
    def move_pointer(self, x: int, y: int) -> None:
        super().move_pointer(x, y)
        raise RuntimeError("injected pointer failure")


def _event(sequence: int = 1) -> GestureEvent:
    return GestureEvent(
        GestureEventType.LEFT_WINK,
        timestamp=1.0,
        source_sequence=sequence,
        duration_ms=120.0,
    )


def _controller(
    qtbot: QtBot,
    *,
    executor: FakeInputExecutor | None = None,
    safety: FakeSafetyApi | None = None,
    clock: Callable[[], float] | None = None,
) -> tuple[LiveInputController, FakeInputExecutor, FakeSafetyApi, list[WindowsEmergencyHotkey]]:
    del qtbot
    fake_executor = executor or FakeInputExecutor()
    fake_safety = safety or FakeSafetyApi()
    hotkeys: list[WindowsEmergencyHotkey] = []

    def hotkey_factory(parent: QObject) -> WindowsEmergencyHotkey:
        application = QCoreApplication.instance()
        assert application is not None
        hotkey = WindowsEmergencyHotkey(
            api=fake_safety,
            application=application,
            parent=parent,
        )
        hotkeys.append(hotkey)
        return hotkey

    controller = LiveInputController(
        default_profile(),
        executor_factory=lambda: fake_executor,
        hotkey_factory=hotkey_factory,
        platform_supported=True,
        clock=clock or (lambda: 2.0),
    )
    return controller, fake_executor, fake_safety, hotkeys


def test_live_input_starts_safe_without_constructing_native_services(qtbot: QtBot) -> None:
    del qtbot
    factories: list[str] = []

    def executor_factory() -> FakeInputExecutor:
        factories.append("executor")
        return FakeInputExecutor()

    def hotkey_factory(parent: QObject) -> WindowsEmergencyHotkey:
        factories.append("hotkey")
        return WindowsEmergencyHotkey(parent=parent)

    controller = LiveInputController(
        default_profile(),
        executor_factory=executor_factory,
        hotkey_factory=hotkey_factory,
        platform_supported=True,
    )

    assert controller.state is LiveInputState.SAFE
    assert controller.snapshot.hotkey_registered is False
    assert factories == []


def test_arm_requires_explicit_nonpersistent_consent(qtbot: QtBot) -> None:
    controller, executor, safety, hotkeys = _controller(qtbot)

    result = controller.arm(False, 101)

    assert not result.success
    assert result.state is LiveInputState.SAFE
    assert safety.registrations == []
    assert hotkeys == []
    assert executor.calls == []


def test_arm_registers_hotkey_preflights_and_releases_before_active(qtbot: QtBot) -> None:
    controller, executor, safety, hotkeys = _controller(qtbot)

    result = controller.arm(True, 101)

    assert result.success and result.released
    assert controller.state is LiveInputState.ARMED
    assert controller.snapshot.hotkey_registered
    assert len(safety.registrations) == 1
    assert len(hotkeys) == 1
    assert executor.calls == [InputCall("release_all"), InputCall("release_all")]


def test_physical_input_preflight_fails_closed_and_unregisters(qtbot: QtBot) -> None:
    safety = FakeSafetyApi(pressed={0x01, 0x11})
    controller, executor, _safety, _hotkeys = _controller(qtbot, safety=safety)

    result = controller.arm(True, 202)

    assert not result.success
    assert controller.state is LiveInputState.SAFE
    assert "left mouse button" in result.message
    assert "Ctrl" in result.message
    assert len(safety.registrations) == 1
    assert len(safety.unregistrations) == 1
    assert executor.calls == []


def test_registration_failure_never_constructs_executor(qtbot: QtBot) -> None:
    safety = FakeSafetyApi(register_result=False)
    controller, executor, _safety, _hotkeys = _controller(qtbot, safety=safety)

    result = controller.arm(True, 303)

    assert not result.success
    assert controller.state is LiveInputState.FAULTED
    assert executor.calls == []
    assert not controller.snapshot.hotkey_registered


def test_armed_event_reaches_executor_but_safe_event_does_not(qtbot: QtBot) -> None:
    controller, executor, _safety, _hotkeys = _controller(qtbot, clock=lambda: 2.0)

    assert controller.dispatch_event(_event()) is None
    assert controller.arm(True, 404).success
    report = controller.dispatch_event(_event())
    stopped = controller.disarm("test")
    assert controller.dispatch_event(_event(2)) is None

    assert report is not None
    assert stopped.success and stopped.released
    assert InputCall("mouse_click", (MouseButton.LEFT,)) in executor.calls
    assert len(_safety.unregistrations) == 1
    assert controller.state is LiveInputState.SAFE


def test_pointer_candidate_reaches_executor_only_while_armed(qtbot: QtBot) -> None:
    controller, executor, _safety, _hotkeys = _controller(qtbot)

    assert not controller.move_pointer(100, 200)
    assert controller.arm(True, 414).success
    assert controller.move_pointer(100, 200)
    assert controller.disarm("test").success
    assert not controller.move_pointer(300, 400)

    assert executor.calls.count(InputCall("move_pointer", (100, 200))) == 1
    assert InputCall("move_pointer", (300, 400)) not in executor.calls


def test_pointer_failure_gates_live_input_and_requests_tracking_pause(qtbot: QtBot) -> None:
    executor = FailMoveExecutor()
    controller, _executor, safety, _hotkeys = _controller(qtbot, executor=executor)
    pauses: list[bool] = []
    controller.tracking_pause_requested.connect(lambda: pauses.append(True))
    assert controller.arm(True, 424).success

    moved = controller.move_pointer(100, 200)

    assert not moved
    assert controller.state is LiveInputState.FAULTED
    assert controller.snapshot.hotkey_registered
    assert "Pointer output failed" in controller.snapshot.message
    assert pauses == [True]
    assert executor.calls[-1] == InputCall("release_all")
    assert safety.unregistrations == []
    assert controller.disarm("recover pointer fault").success
    assert len(safety.unregistrations) == 1


def test_emergency_stop_releases_unregisters_and_requests_tracking_pause(qtbot: QtBot) -> None:
    controller, executor, safety, hotkeys = _controller(qtbot, clock=lambda: 2.0)
    pauses: list[bool] = []
    controller.tracking_pause_requested.connect(lambda: pauses.append(True))
    assert controller.arm(True, 505).success
    controller.dispatch_event(_event())

    hotkeys[0].triggered.emit()

    assert controller.state is LiveInputState.SAFE
    assert not controller.snapshot.hotkey_registered
    assert pauses == [True]
    assert len(safety.unregistrations) == 1
    assert executor.calls[-1] == InputCall("release_all")


def test_release_failure_faults_and_keeps_registered_emergency_hotkey(qtbot: QtBot) -> None:
    executor = FailReleaseExecutor()
    controller, _executor, safety, _hotkeys = _controller(qtbot, executor=executor)

    result = controller.arm(True, 606)

    assert not result.success
    assert controller.state is LiveInputState.FAULTED
    assert controller.snapshot.hotkey_registered
    assert safety.unregistrations == []
    controller.close()
    assert len(safety.unregistrations) == 1


def test_profile_change_disarms_and_requires_consent_again(qtbot: QtBot) -> None:
    controller, _executor, safety, _hotkeys = _controller(qtbot)
    assert controller.arm(True, 707).success

    changed = controller.activate_profile(disabled_profile("Quiet"))

    assert changed.success
    assert controller.state is LiveInputState.SAFE
    assert controller.snapshot.profile_name == "Quiet"
    assert len(safety.unregistrations) == 1


def test_failed_profile_transition_stays_faulted_until_pending_profile_is_synced(
    qtbot: QtBot,
) -> None:
    executor = FailThirdReleaseExecutor()
    controller, _executor, safety, _hotkeys = _controller(qtbot, executor=executor)
    assert controller.arm(True, 717).success

    changed = controller.activate_profile(disabled_profile("Quiet"))

    assert not changed.success
    faulted_snapshot = controller.snapshot
    assert faulted_snapshot.state.value == "faulted"
    assert faulted_snapshot.profile_name == "Default"
    assert faulted_snapshot.hotkey_registered

    recovered = controller.disarm("retry profile synchronization")

    assert recovered.success
    recovered_snapshot = controller.snapshot
    assert recovered_snapshot.state.value == "safe"
    assert recovered_snapshot.profile_name == "Quiet"
    assert not recovered_snapshot.hotkey_registered
    assert len(safety.unregistrations) == 1


def test_close_is_terminal_and_releases_before_hotkey_cleanup(qtbot: QtBot) -> None:
    controller, executor, safety, _hotkeys = _controller(qtbot)
    assert controller.arm(True, 808).success

    result = controller.close()
    rearm = controller.arm(True, 808)

    assert result.success and result.released
    assert not rearm.success
    assert controller.state is LiveInputState.CLOSED
    assert executor.calls[-1] == InputCall("release_all")
    assert len(safety.unregistrations) == 1


def test_unsupported_platform_stays_safe_without_factories(qtbot: QtBot) -> None:
    del qtbot
    factories: list[str] = []

    def executor_factory() -> FakeInputExecutor:
        factories.append("executor")
        return FakeInputExecutor()

    def hotkey_factory(parent: QObject) -> WindowsEmergencyHotkey:
        factories.append("hotkey")
        return WindowsEmergencyHotkey(parent=parent)

    controller = LiveInputController(
        default_profile(),
        executor_factory=executor_factory,
        hotkey_factory=hotkey_factory,
        platform_supported=False,
    )

    result = controller.arm(True, 909)

    assert not result.success
    assert controller.state is LiveInputState.SAFE
    assert factories == []
