"""Qt bridge tests for fake-only action simulation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import pytest
from pytestqt.qtbot import QtBot

from meyes.bindings.defaults import default_profile, disabled_profile
from meyes.bindings.manager import BindingManager
from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.domain.actions import Action, MouseButton, MouseDownAction
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.input.fake import FakeInputExecutor, InputCall
from meyes.services.action_dispatcher import (
    DispatcherSnapshot,
    DispatcherState,
    DispatchReport,
    DispatchStatus,
    LifecycleReport,
)
from meyes.ui.action_simulation import (
    ActionSimulationController,
    simulation_report,
    simulation_snapshot,
)


@dataclass(slots=True)
class ManualClock:
    value: float

    def __call__(self) -> float:
        return self.value


class FailingClickExecutor(FakeInputExecutor):
    def mouse_click(self, button: MouseButton) -> None:
        super().mouse_click(button)
        raise RuntimeError("injected simulation failure")


class ReentrantCloseExecutor(FakeInputExecutor):
    def __init__(self) -> None:
        super().__init__()
        self.controller: ActionSimulationController | None = None
        self.nested_close: LifecycleReport | None = None

    def mouse_click(self, button: MouseButton) -> None:
        super().mouse_click(button)
        assert self.controller is not None
        self.nested_close = self.controller.close()


def event(
    event_type: GestureEventType,
    *,
    timestamp: float,
    sequence: int,
    duration_ms: float = 0.0,
) -> GestureEvent:
    return GestureEvent(
        type=event_type,
        timestamp=timestamp,
        source_sequence=sequence,
        duration_ms=duration_ms,
    )


def manager_with(updates: Mapping[BindableGesture, Action]) -> BindingManager:
    bindings = dict(default_profile().bindings)
    bindings.update(updates)
    return BindingManager(BindingProfile(profile_name="Simulation test", bindings=bindings))


def assert_controller_state(
    controller: ActionSimulationController,
    expected: DispatcherState,
) -> None:
    assert controller.state is expected


def assert_timer_state(controller: ActionSimulationController, *, active: bool) -> None:
    assert controller.timer_active is active


def assert_held_buttons(
    executor: FakeInputExecutor,
    expected: set[MouseButton],
) -> None:
    assert executor.held_buttons == expected


def assert_simulated_calls(
    controller: ActionSimulationController,
    expected: tuple[InputCall, ...],
) -> None:
    assert controller.simulated_calls == expected


def test_initial_pause_gates_events_and_start_runs_release_preflight(qtbot: QtBot) -> None:
    clock = ManualClock(1.0)
    executor = FakeInputExecutor()
    controller = ActionSimulationController(executor=executor, clock=clock)

    assert_controller_state(controller, DispatcherState.PAUSED)
    inactive = controller.dispatch_event(
        event(GestureEventType.LEFT_WINK, timestamp=1.0, sequence=1)
    )
    assert inactive is not None
    assert inactive.status is DispatchStatus.INACTIVE
    assert_simulated_calls(controller, ())
    assert executor.calls == []

    with qtbot.waitSignal(controller.lifecycle_reported, timeout=1000) as lifecycle_signal:
        started = controller.start()

    assert lifecycle_signal.args == [started]
    assert started == LifecycleReport(
        success=True,
        state=DispatcherState.ACTIVE,
        released=True,
    )
    assert_controller_state(controller, DispatcherState.ACTIVE)
    assert executor.release_all_calls == 1
    assert executor.calls == []
    assert_simulated_calls(controller, (InputCall("release_all"),))

    clock.value = 2.0
    executed = controller.dispatch_event(
        event(GestureEventType.LEFT_WINK, timestamp=2.0, sequence=2)
    )
    assert executed is not None
    assert executed.status is DispatchStatus.EXECUTED
    assert controller.simulated_calls[-1] == InputCall("mouse_click", (MouseButton.LEFT,))


def test_dispatch_emits_executed_and_duplicate_reports_without_replaying(
    qtbot: QtBot,
) -> None:
    del qtbot
    clock = ManualClock(3.0)
    executor = FakeInputExecutor()
    controller = ActionSimulationController(executor=executor, clock=clock)
    controller.start()
    reports: list[DispatchReport] = []
    input_calls: list[InputCall] = []
    snapshots: list[DispatcherSnapshot] = []
    controller.report_emitted.connect(reports.append)
    controller.input_call_emitted.connect(input_calls.append)
    controller.snapshot_changed.connect(snapshots.append)
    wink = event(GestureEventType.RIGHT_WINK, timestamp=3.0, sequence=8)

    first = controller.dispatch_event(wink)
    duplicate = controller.dispatch_event(wink)

    assert first is not None
    assert duplicate is not None
    assert [report.status for report in reports] == [
        DispatchStatus.EXECUTED,
        DispatchStatus.DUPLICATE,
    ]
    assert reports == [first, duplicate]
    assert input_calls == [InputCall("mouse_click", (MouseButton.RIGHT,))]
    assert executor.calls == []
    assert len(snapshots) == 2
    assert all(snapshot.state is DispatcherState.ACTIVE for snapshot in snapshots)


def test_manual_clock_drives_continuous_start_poll_and_end_deterministically(
    qtbot: QtBot,
) -> None:
    del qtbot
    clock = ManualClock(10.0)
    controller = ActionSimulationController(clock=clock)
    controller.start()
    reports: list[DispatchReport] = []
    calls: list[InputCall] = []
    controller.report_emitted.connect(reports.append)
    controller.input_call_emitted.connect(calls.append)

    started = controller.dispatch_event(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, timestamp=10.0, sequence=7)
    )

    assert started is not None
    assert started.status is DispatchStatus.CONTINUOUS_STARTED
    assert controller.snapshot.next_poll_deadline == pytest.approx(10.1)
    assert_timer_state(controller, active=True)
    reports.clear()

    clock.value = 10.099
    controller.poll_now()
    assert reports == []
    assert calls == []
    assert_timer_state(controller, active=True)

    clock.value = 10.1
    controller.poll_now()
    assert [report.status for report in reports] == [DispatchStatus.CONTINUOUS_TICK]
    assert calls == [InputCall("mouse_scroll", (-2,))]
    assert controller.snapshot.next_poll_deadline == pytest.approx(10.2)

    ended = controller.dispatch_event(
        event(
            GestureEventType.LEFT_TEMPLE_HOLD_END,
            timestamp=10.1,
            sequence=7,
            duration_ms=100.0,
        )
    )
    assert ended is not None
    assert ended.status is DispatchStatus.HOLD_ENDED
    assert controller.snapshot.active_holds == ()
    assert controller.snapshot.next_poll_deadline is None
    assert_timer_state(controller, active=False)

    clock.value = 11.0
    controller.poll_now()
    assert calls == [InputCall("mouse_scroll", (-2,))]


def test_pause_stops_timer_and_releases_all_fake_held_state(qtbot: QtBot) -> None:
    del qtbot
    clock = ManualClock(20.0)
    executor = FakeInputExecutor()
    controller = ActionSimulationController(
        manager_with({BindableGesture.RIGHT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT)}),
        executor=executor,
        clock=clock,
    )
    controller.start()
    controller.dispatch_event(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, timestamp=20.0, sequence=1)
    )
    controller.dispatch_event(
        event(GestureEventType.RIGHT_TEMPLE_HOLD_START, timestamp=20.0, sequence=1)
    )
    assert_timer_state(controller, active=True)
    assert_held_buttons(executor, {MouseButton.LEFT})

    paused = controller.pause("test pause")

    assert paused.success
    assert paused.released
    assert paused.state is DispatcherState.PAUSED
    assert controller.snapshot.active_holds == ()
    assert controller.snapshot.next_poll_deadline is None
    assert_timer_state(controller, active=False)
    assert_held_buttons(executor, set())
    assert executor.release_all_calls == 2
    assert executor.calls == []
    assert controller.simulated_calls[-2:] == (
        InputCall("mouse_up", (MouseButton.LEFT,)),
        InputCall("release_all"),
    )


def test_profile_activation_releases_holds_stops_timer_and_does_not_rearm(
    qtbot: QtBot,
) -> None:
    del qtbot
    clock = ManualClock(30.0)
    executor = FakeInputExecutor()
    original = manager_with(
        {BindableGesture.RIGHT_TEMPLE_HOLD: MouseDownAction(button=MouseButton.LEFT)}
    )
    controller = ActionSimulationController(original, executor=executor, clock=clock)
    controller.start()
    controller.dispatch_event(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, timestamp=30.0, sequence=1)
    )
    controller.dispatch_event(
        event(GestureEventType.RIGHT_TEMPLE_HOLD_START, timestamp=30.0, sequence=1)
    )
    assert_timer_state(controller, active=True)
    assert_held_buttons(executor, {MouseButton.LEFT})
    previous_snapshot = controller.active_profile
    replacement = disabled_profile("Replacement")

    activated = controller.activate_profile(replacement)

    assert activated == LifecycleReport(
        success=True,
        state=DispatcherState.PAUSED,
        released=True,
    )
    assert controller.active_profile == replacement
    assert controller.active_profile is not replacement
    assert previous_snapshot.profile_name == "Simulation test"
    assert controller.snapshot.active_holds == ()
    assert controller.snapshot.next_poll_deadline is None
    assert_timer_state(controller, active=False)
    assert_held_buttons(executor, set())
    assert executor.release_all_calls == 2
    assert controller.simulated_calls[-2:] == (
        InputCall("mouse_up", (MouseButton.LEFT,)),
        InputCall("release_all"),
    )

    clock.value = 31.0
    suppressed = controller.dispatch_event(
        event(GestureEventType.LEFT_WINK, timestamp=31.0, sequence=2)
    )
    assert suppressed is not None
    assert suppressed.status is DispatchStatus.INACTIVE
    assert controller.state is DispatcherState.PAUSED
    assert InputCall("mouse_click", (MouseButton.LEFT,)) not in controller.simulated_calls


def test_qt_object_boundary_contains_malformed_payloads(qtbot: QtBot) -> None:
    del qtbot
    controller = ActionSimulationController(clock=ManualClock(1.0))
    reports: list[DispatchReport] = []
    snapshots: list[DispatcherSnapshot] = []
    controller.report_emitted.connect(reports.append)
    controller.snapshot_changed.connect(snapshots.append)

    controller.handle_event(None)
    controller.handle_event({"type": "LEFT_WINK"})
    controller.handle_event(object())

    assert controller.state is DispatcherState.PAUSED
    assert controller.simulated_calls == ()
    assert reports == []
    assert snapshots == []
    with pytest.raises(TypeError, match="Expected GestureEvent"):
        controller.dispatch_event(cast(GestureEvent, object()))
    with pytest.raises(TypeError, match="Expected DispatchReport"):
        simulation_report(object())
    with pytest.raises(TypeError, match="Expected DispatcherSnapshot"):
        simulation_snapshot(object())


def test_recent_call_records_are_bounded_and_executor_records_are_drained(
    qtbot: QtBot,
) -> None:
    del qtbot
    clock = ManualClock(100.0)
    executor = FakeInputExecutor()
    controller = ActionSimulationController(executor=executor, clock=clock)
    emitted: list[InputCall] = []
    controller.input_call_emitted.connect(emitted.append)
    controller.start()

    for sequence in range(1, 106):
        clock.value = 100.0 + sequence
        report = controller.dispatch_event(
            event(
                GestureEventType.LEFT_WINK,
                timestamp=clock.value,
                sequence=sequence,
            )
        )
        assert report is not None
        assert report.status is DispatchStatus.EXECUTED
        assert executor.calls == []

    click = InputCall("mouse_click", (MouseButton.LEFT,))
    assert emitted == [InputCall("release_all"), *([click] * 105)]
    assert len(controller.simulated_calls) == 100
    assert controller.simulated_calls == (click,) * 100
    assert executor.calls == []


def test_executor_fault_is_contained_and_requests_tracking_pause(qtbot: QtBot) -> None:
    del qtbot
    clock = ManualClock(1.0)
    executor = FailingClickExecutor()
    controller = ActionSimulationController(executor=executor, clock=clock)
    controller.start()
    reports: list[DispatchReport] = []
    pause_requests: list[str] = []
    controller.report_emitted.connect(reports.append)
    controller.tracking_pause_requested.connect(lambda: pause_requests.append("pause"))

    report = controller.dispatch_event(event(GestureEventType.LEFT_WINK, timestamp=1.0, sequence=1))

    assert report is not None
    assert report.status is DispatchStatus.FAULTED
    assert reports == [report]
    assert controller.state is DispatcherState.FAULTED
    assert controller.snapshot.fault is not None
    assert controller.snapshot.fault.operation == "mouse_click"
    assert pause_requests == ["pause"]
    assert not controller.timer_active
    assert executor.release_all_calls == 2
    assert executor.calls == []
    assert controller.simulated_calls[-2:] == (
        InputCall("mouse_click", (MouseButton.LEFT,)),
        InputCall("release_all"),
    )


def test_close_is_terminal_and_blocks_future_start_and_dispatch(qtbot: QtBot) -> None:
    del qtbot
    clock = ManualClock(1.0)
    executor = FakeInputExecutor()
    controller = ActionSimulationController(executor=executor, clock=clock)
    controller.start()

    closed = controller.close()
    restarted = controller.start()
    clock.value = 2.0
    ignored = controller.dispatch_event(
        event(GestureEventType.LEFT_WINK, timestamp=2.0, sequence=1)
    )

    assert closed.success
    assert closed.released
    assert closed.state is DispatcherState.CLOSED
    assert restarted.success is False
    assert restarted.state is DispatcherState.CLOSED
    assert ignored is not None
    assert ignored.status is DispatchStatus.INACTIVE
    assert ignored.state is DispatcherState.CLOSED
    assert controller.state is DispatcherState.CLOSED
    assert not controller.timer_active
    assert executor.release_all_calls == 2
    assert InputCall("mouse_click", (MouseButton.LEFT,)) not in controller.simulated_calls


def test_reentrant_close_defers_release_and_preserves_terminal_state(qtbot: QtBot) -> None:
    del qtbot
    clock = ManualClock(5.0)
    executor = ReentrantCloseExecutor()
    controller = ActionSimulationController(executor=executor, clock=clock)
    executor.controller = controller
    controller.start()
    lifecycle_reports: list[LifecycleReport] = []
    controller.lifecycle_reported.connect(lifecycle_reports.append)

    outer = controller.dispatch_event(event(GestureEventType.LEFT_WINK, timestamp=5.0, sequence=1))

    assert executor.nested_close is not None
    assert executor.nested_close.success
    assert executor.nested_close.released is False
    assert executor.nested_close.state is DispatcherState.CLOSED
    assert lifecycle_reports == [executor.nested_close]
    assert outer is not None
    assert outer.status is DispatchStatus.INACTIVE
    assert outer.state is DispatcherState.CLOSED
    assert controller.state is DispatcherState.CLOSED
    assert not controller.timer_active
    assert executor.release_all_calls == 2
    assert executor.calls == []
    assert controller.simulated_calls[-2:] == (
        InputCall("mouse_click", (MouseButton.LEFT,)),
        InputCall("release_all"),
    )
