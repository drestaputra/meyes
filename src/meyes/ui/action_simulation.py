"""Qt-owned fake-only action dispatch bridge for Safe Mode diagnostics."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from math import ceil, isfinite

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from meyes.bindings.manager import BindingManager
from meyes.domain.events import GestureEvent
from meyes.input.fake import FakeInputExecutor, InputCall
from meyes.services.action_dispatcher import (
    ActionDispatcher,
    DispatcherSnapshot,
    DispatcherState,
    DispatchReport,
    LifecycleReport,
)

_MAX_QT_TIMER_INTERVAL_MS = 2_147_483_647
_MAX_RECENT_CALLS = 100


class ActionSimulationController(QObject):
    """Drive the dispatcher on Qt's owning thread without touching OS input."""

    report_emitted = Signal(object)
    lifecycle_reported = Signal(object)
    snapshot_changed = Signal(object)
    input_call_emitted = Signal(object)
    tracking_pause_requested = Signal()
    tracking_resume_requested = Signal()

    def __init__(
        self,
        bindings: BindingManager | None = None,
        *,
        executor: FakeInputExecutor | None = None,
        clock: Callable[[], float] = time.monotonic,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if executor is not None and not isinstance(executor, FakeInputExecutor):
            raise TypeError("Safe Mode simulation requires FakeInputExecutor")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._executor = executor or FakeInputExecutor()
        self._clock = clock
        self._dispatcher = ActionDispatcher(
            bindings or BindingManager(),
            self._executor,
            tracking_control=self,
            safe_mode=True,
        )
        self._recent_calls: deque[InputCall] = deque(maxlen=_MAX_RECENT_CALLS)
        self._poll_timer = QTimer(self)
        self._poll_timer.setSingleShot(True)
        self._poll_timer.timeout.connect(self.poll_now)

    @property
    def state(self) -> DispatcherState:
        """Return the current fake dispatcher state."""
        return self._dispatcher.state

    @property
    def snapshot(self) -> DispatcherSnapshot:
        """Return an immutable state snapshot for diagnostics."""
        return self._dispatcher.snapshot

    @property
    def simulated_calls(self) -> tuple[InputCall, ...]:
        """Return the latest bounded fake primitive trace."""
        return tuple(self._recent_calls)

    @property
    def timer_active(self) -> bool:
        """Report whether a continuous-action poll is scheduled."""
        return self._poll_timer.isActive()

    def start(self) -> LifecycleReport:
        """Arm fake dispatch after a release preflight and schedule pending work."""
        if self._dispatcher.state is DispatcherState.ACTIVE:
            report = LifecycleReport(
                success=True,
                state=DispatcherState.ACTIVE,
                released=False,
            )
            self.lifecycle_reported.emit(report)
            self._emit_snapshot()
            self._schedule_next_poll()
            return report
        return self._run_lifecycle(self._dispatcher.arm)

    def pause(self, reason: str = "runtime pause") -> LifecycleReport:
        """Stop polling, gate dispatch, and release all fake held state."""
        self._poll_timer.stop()
        return self._run_lifecycle(lambda: self._dispatcher.pause(reason))

    def stop(self, reason: str = "runtime stop") -> LifecycleReport:
        """Pause safely without terminating a future camera restart."""
        return self.pause(reason)

    def recover(self) -> LifecycleReport:
        """Retry fake cleanup after a fault and remain paused."""
        self._poll_timer.stop()
        return self._run_lifecycle(self._dispatcher.recover)

    def close(self) -> LifecycleReport:
        """Enter terminal state before the vision and camera workers shut down."""
        self._poll_timer.stop()
        return self._run_lifecycle(self._dispatcher.close)

    def dispatch_event(self, event: GestureEvent) -> DispatchReport | None:
        """Dispatch one semantic event using the adapter's monotonic clock."""
        if not isinstance(event, GestureEvent):
            raise TypeError("Expected GestureEvent")
        timestamp = self._safe_timestamp()
        if timestamp is None:
            return None
        report = self._dispatcher.dispatch(event, current_timestamp=timestamp)
        self._emit_new_calls()
        self.report_emitted.emit(report)
        self._emit_snapshot()
        self._schedule_next_poll()
        return report

    @Slot(object)
    def handle_event(self, payload: object) -> None:
        """Validate the Qt object-signal boundary and dispatch one event."""
        if not isinstance(payload, GestureEvent):
            return
        self.dispatch_event(payload)

    @Slot()
    def poll_now(self) -> None:
        """Run one no-catch-up poll at the injected monotonic time."""
        self._poll_timer.stop()
        timestamp = self._safe_timestamp()
        if timestamp is None:
            return
        reports = self._dispatcher.poll(timestamp)
        self._emit_new_calls()
        for report in reports:
            self.report_emitted.emit(report)
        self._emit_snapshot()
        self._schedule_next_poll()

    def pause_tracking(self) -> None:
        """Translate dispatcher lifecycle intent into a queued runtime request."""
        self.tracking_pause_requested.emit()

    def resume_tracking(self) -> None:
        """Translate dispatcher lifecycle intent into a queued runtime request."""
        self.tracking_resume_requested.emit()

    def _run_lifecycle(self, operation: Callable[[], LifecycleReport]) -> LifecycleReport:
        report = operation()
        self._emit_new_calls()
        self.lifecycle_reported.emit(report)
        self._emit_snapshot()
        self._schedule_next_poll()
        return report

    def _safe_timestamp(self) -> float | None:
        try:
            value = self._clock()
        except Exception:
            self.pause("simulation clock failure")
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.pause("invalid simulation clock")
            return None
        timestamp = float(value)
        if not isfinite(timestamp) or timestamp < 0:
            self.pause("invalid simulation clock")
            return None
        return timestamp

    def _schedule_next_poll(self) -> None:
        self._poll_timer.stop()
        if self._dispatcher.state is not DispatcherState.ACTIVE:
            return
        deadline = self._dispatcher.next_poll_deadline
        if deadline is None:
            return
        timestamp = self._safe_timestamp()
        if timestamp is None or self._dispatcher.state is not DispatcherState.ACTIVE:
            return
        delay_ms = max(1, ceil(max(0.0, deadline - timestamp) * 1000.0))
        self._poll_timer.start(min(delay_ms, _MAX_QT_TIMER_INTERVAL_MS))

    def _emit_new_calls(self) -> None:
        for call in self._executor.drain_calls():
            self._recent_calls.append(call)
            self.input_call_emitted.emit(call)

    def _emit_snapshot(self) -> None:
        self.snapshot_changed.emit(self._dispatcher.snapshot)


def simulation_report(payload: object) -> DispatchReport:
    """Validate an action simulation report crossing a Qt object signal."""
    if not isinstance(payload, DispatchReport):
        raise TypeError("Expected DispatchReport")
    return payload


def simulation_snapshot(payload: object) -> DispatcherSnapshot:
    """Validate a dispatcher snapshot crossing a Qt object signal."""
    if not isinstance(payload, DispatcherSnapshot):
        raise TypeError("Expected DispatcherSnapshot")
    return payload


def simulation_input_call(payload: object) -> InputCall:
    """Validate a fake primitive record crossing a Qt object signal."""
    if not isinstance(payload, InputCall):
        raise TypeError("Expected InputCall")
    return payload
