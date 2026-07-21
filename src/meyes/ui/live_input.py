"""Explicitly armed Qt runtime for real Windows input execution."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from math import ceil, isfinite

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from meyes.bindings.manager import BindingManager
from meyes.bindings.models import BindingProfile
from meyes.domain.events import GestureEvent
from meyes.input.interface import InputExecutor
from meyes.input.windows_safety import EMERGENCY_HOTKEY_LABEL, WindowsEmergencyHotkey
from meyes.input.windows_sendinput import WindowsSendInputExecutor
from meyes.services.action_dispatcher import (
    ActionDispatcher,
    DispatcherFault,
    DispatcherState,
    DispatchReport,
    LifecycleReport,
)

_MAX_QT_TIMER_INTERVAL_MS = 2_147_483_647

InputExecutorFactory = Callable[[], InputExecutor]
EmergencyHotkeyFactory = Callable[[QObject], WindowsEmergencyHotkey]


class LiveInputState(StrEnum):
    """User-facing state of the non-persistent live-input session."""

    SAFE = "safe"
    ARMED = "armed"
    FAULTED = "faulted"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class LiveInputSnapshot:
    """Immutable status suitable for a persistent safety UI."""

    state: LiveInputState
    platform_supported: bool
    profile_name: str
    hotkey_registered: bool
    active_holds: tuple[str, ...]
    fault: DispatcherFault | None
    message: str


@dataclass(frozen=True, slots=True)
class LiveInputResult:
    """Sanitized outcome of one requested live-input lifecycle change."""

    success: bool
    state: LiveInputState
    message: str
    released: bool = False


class LiveInputController(QObject):
    """Own a lazily-created SendInput dispatcher behind explicit safety gates."""

    snapshot_changed = Signal(object)
    report_emitted = Signal(object)
    lifecycle_finished = Signal(object)
    tracking_pause_requested = Signal()
    tracking_resume_requested = Signal()

    def __init__(
        self,
        active_profile: BindingProfile,
        *,
        executor_factory: InputExecutorFactory = WindowsSendInputExecutor,
        hotkey_factory: EmergencyHotkeyFactory | None = None,
        platform_supported: bool | None = None,
        clock: Callable[[], float] = time.monotonic,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(active_profile, BindingProfile):
            raise TypeError("Expected BindingProfile")
        if not callable(executor_factory):
            raise TypeError("executor_factory must be callable")
        if hotkey_factory is not None and not callable(hotkey_factory):
            raise TypeError("hotkey_factory must be callable")
        if platform_supported is not None and not isinstance(platform_supported, bool):
            raise TypeError("platform_supported must be a bool")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._profile = BindingManager(active_profile).active_profile
        self._executor_factory = executor_factory
        self._hotkey_factory = hotkey_factory or _create_emergency_hotkey
        self._platform_supported = (
            os.name == "nt" if platform_supported is None else platform_supported
        )
        self._clock = clock
        self._state = LiveInputState.SAFE
        self._message = "Safe Mode: Windows input is disconnected."
        self._pending_profile: BindingProfile | None = None
        self._executor: InputExecutor | None = None
        self._dispatcher: ActionDispatcher | None = None
        self._hotkey: WindowsEmergencyHotkey | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setSingleShot(True)
        self._poll_timer.timeout.connect(self.poll_now)

    @property
    def state(self) -> LiveInputState:
        return self._state

    @property
    def snapshot(self) -> LiveInputSnapshot:
        dispatcher = self._dispatcher
        active_holds = (
            tuple(gesture.value for gesture in dispatcher.active_holds)
            if dispatcher is not None
            else ()
        )
        return LiveInputSnapshot(
            state=self._state,
            platform_supported=self._platform_supported,
            profile_name=self._profile.profile_name,
            hotkey_registered=self._hotkey is not None and self._hotkey.registered,
            active_holds=active_holds,
            fault=dispatcher.fault if dispatcher is not None else None,
            message=self._message,
        )

    @property
    def timer_active(self) -> bool:
        return self._poll_timer.isActive()

    def arm(self, consent_granted: bool, window_id: int) -> LiveInputResult:
        """Arm one volatile session only after explicit modal consent."""
        if self._state is LiveInputState.CLOSED:
            return self._finish(False, "Live Input is closed for this application session.")
        if not self._platform_supported:
            return self._finish(False, "Live Input requires Windows 10 or Windows 11.")
        if consent_granted is not True:
            return self._finish(
                False,
                "Confirm Live Input in the per-session dialog to continue.",
            )
        if self._state is LiveInputState.ARMED:
            return self._finish(True, "Live Input is already armed.")
        if self._state is LiveInputState.FAULTED:
            return self._finish(False, "Recover the Live Input fault before arming again.")

        try:
            hotkey = self._ensure_hotkey()
            hotkey.register(window_id)
        except Exception as error:
            self._state = LiveInputState.FAULTED
            return self._finish(
                False,
                f"Emergency shortcut registration failed ({type(error).__name__}).",
            )

        try:
            preflight = hotkey.physical_input_preflight()
        except Exception as error:
            return self._fail_after_registered_hotkey(
                f"Physical-input preflight failed ({type(error).__name__})."
            )
        if not preflight.clear:
            pressed = ", ".join(preflight.pressed)
            return self._fail_after_registered_hotkey(
                f"Release these physical inputs before arming: {pressed}."
            )

        try:
            dispatcher = self._ensure_dispatcher()
            epoch = dispatcher.begin_event_epoch()
            report = dispatcher.arm() if epoch.success else epoch
        except Exception as error:
            return self._fail_after_registered_hotkey(
                f"Live executor startup failed ({type(error).__name__})."
            )
        if not report.success:
            self._state = LiveInputState.FAULTED
            self._message = "Live executor release preflight failed; input remains gated."
            self._emit_lifecycle(report)
            return self._finish(False, self._message, released=report.released)

        self._state = LiveInputState.ARMED
        self._message = f"LIVE INPUT ARMED. Press {EMERGENCY_HOTKEY_LABEL} to stop immediately."
        self._emit_lifecycle(report)
        self._schedule_next_poll()
        return self._finish(True, self._message, released=report.released)

    def disarm(self, reason: str = "user request") -> LiveInputResult:
        """Gate and release live input, then unregister the global shortcut."""
        if self._state is LiveInputState.CLOSED:
            return self._finish(False, "Live Input is closed for this application session.")
        self._poll_timer.stop()
        released = False
        dispatcher = self._dispatcher
        if dispatcher is not None:
            report = (
                dispatcher.recover()
                if dispatcher.state is DispatcherState.FAULTED
                else dispatcher.pause(reason)
            )
            released = report.released
            self._emit_lifecycle(report)
            if not report.success:
                self._state = LiveInputState.FAULTED
                return self._finish(
                    False,
                    "Live Input release failed; tracking is paused and recovery is required.",
                    released=released,
                )
        synchronized = self._apply_pending_profile()
        if synchronized is not None and not synchronized.success:
            self._state = LiveInputState.FAULTED
            return self._finish(
                False,
                "Live Input recovered its held state but could not synchronize the pending "
                "profile; retry recovery.",
                released=released,
            )
        try:
            self._close_hotkey()
        except Exception as error:
            self._state = LiveInputState.FAULTED
            return self._finish(
                False,
                f"Emergency shortcut cleanup failed ({type(error).__name__}); retry recovery.",
                released=released,
            )
        self._state = LiveInputState.SAFE
        return self._finish(
            True,
            f"Safe Mode restored ({reason}); Windows input is disconnected.",
            released=released,
        )

    @Slot()
    def emergency_stop(self) -> None:
        """Release first, request tracking pause, and invalidate session consent."""
        result = self.disarm("emergency shortcut")
        self.tracking_pause_requested.emit()
        if not result.success:
            self._message = f"EMERGENCY STOP FAULT: {result.message}"
            self.snapshot_changed.emit(self.snapshot)

    def activate_profile(self, profile: BindingProfile) -> LiveInputResult:
        """Disarm before replacing the profile owned by the live dispatcher."""
        if not isinstance(profile, BindingProfile):
            raise TypeError("Expected BindingProfile")
        if self._state is LiveInputState.CLOSED:
            return self._finish(False, "Live Input is closed for this application session.")
        self._pending_profile = BindingManager(profile).active_profile
        stopped = self.disarm("profile transition")
        if not stopped.success:
            return stopped
        return self._finish(
            True,
            "Profile synchronized in Safe Mode; explicit consent is required to re-arm.",
            released=stopped.released,
        )

    def close(self) -> LiveInputResult:
        """Enter a terminal gate and make best-effort release and hotkey cleanup."""
        if self._state is LiveInputState.CLOSED:
            return self._finish(True, self._message)
        self._poll_timer.stop()
        errors: list[str] = []
        released = False
        if self._dispatcher is not None:
            report = self._dispatcher.close()
            released = report.released
            self._emit_lifecycle(report)
            if not report.success:
                errors.append("input release")
        try:
            self._close_hotkey()
        except Exception:
            errors.append("emergency shortcut cleanup")
        self._state = LiveInputState.CLOSED
        if errors:
            return self._finish(
                False,
                f"Live Input closed after failed {', '.join(errors)}.",
                released=released,
            )
        return self._finish(True, "Live Input closed and all owned input was released.", released)

    def dispatch_event(self, event: GestureEvent) -> DispatchReport | None:
        """Dispatch one semantic event only while the explicit session is armed."""
        if not isinstance(event, GestureEvent):
            raise TypeError("Expected GestureEvent")
        if self._state is not LiveInputState.ARMED or self._dispatcher is None:
            return None
        timestamp = self._safe_timestamp()
        if timestamp is None:
            return None
        report = self._dispatcher.dispatch(event, current_timestamp=timestamp)
        self.report_emitted.emit(report)
        self._observe_dispatcher()
        self._schedule_next_poll()
        return report

    @Slot(int, int)
    def move_pointer(self, x: int, y: int) -> bool:
        """Move to one calibrated pixel only while this session remains armed."""
        if self._state is not LiveInputState.ARMED or self._executor is None:
            return False
        try:
            self._executor.move_pointer(x, y)
        except Exception as error:
            self._fault_pointer_output(error)
            return False
        return True

    @Slot(object)
    def handle_event(self, payload: object) -> None:
        if isinstance(payload, GestureEvent):
            self.dispatch_event(payload)

    @Slot()
    def poll_now(self) -> None:
        self._poll_timer.stop()
        if self._state is not LiveInputState.ARMED or self._dispatcher is None:
            return
        timestamp = self._safe_timestamp()
        if timestamp is None:
            return
        for report in self._dispatcher.poll(timestamp):
            self.report_emitted.emit(report)
        self._observe_dispatcher()
        self._schedule_next_poll()

    def pause_tracking(self) -> None:
        self.tracking_pause_requested.emit()

    def resume_tracking(self) -> None:
        self.tracking_resume_requested.emit()

    def _ensure_hotkey(self) -> WindowsEmergencyHotkey:
        if self._hotkey is None:
            hotkey = self._hotkey_factory(self)
            if not isinstance(hotkey, WindowsEmergencyHotkey):
                raise TypeError("hotkey_factory must return WindowsEmergencyHotkey")
            hotkey.triggered.connect(self.emergency_stop)
            self._hotkey = hotkey
        return self._hotkey

    def _ensure_dispatcher(self) -> ActionDispatcher:
        if self._dispatcher is not None:
            return self._dispatcher
        executor = self._executor_factory()
        if not isinstance(executor, InputExecutor):
            raise TypeError("executor_factory must return InputExecutor")
        self._executor = executor
        self._dispatcher = ActionDispatcher(
            BindingManager(self._profile),
            executor,
            tracking_control=self,
            safe_mode=True,
        )
        return self._dispatcher

    def _close_hotkey(self) -> None:
        if self._hotkey is not None:
            self._hotkey.close()

    def _apply_pending_profile(self) -> LifecycleReport | None:
        candidate = self._pending_profile
        if candidate is None:
            return None
        dispatcher = self._dispatcher
        if dispatcher is not None:
            report = dispatcher.activate_profile(candidate)
            self._emit_lifecycle(report)
            if not report.success:
                return report
        self._profile = candidate
        self._pending_profile = None
        return LifecycleReport(
            success=True,
            state=DispatcherState.PAUSED,
            released=dispatcher is not None,
        )

    def _fail_after_registered_hotkey(self, message: str) -> LiveInputResult:
        try:
            self._close_hotkey()
        except Exception as error:
            self._state = LiveInputState.FAULTED
            return self._finish(
                False,
                f"{message} Emergency cleanup also failed ({type(error).__name__}).",
            )
        self._state = LiveInputState.SAFE
        return self._finish(False, message)

    def _safe_timestamp(self) -> float | None:
        try:
            value = self._clock()
        except Exception:
            self.emergency_stop()
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.emergency_stop()
            return None
        timestamp = float(value)
        if not isfinite(timestamp) or timestamp < 0:
            self.emergency_stop()
            return None
        return timestamp

    def _observe_dispatcher(self) -> None:
        if self._dispatcher is None or self._dispatcher.state is not DispatcherState.FAULTED:
            return
        self._poll_timer.stop()
        self._state = LiveInputState.FAULTED
        self._message = "Live Input faulted, released owned input, and requested tracking pause."
        self.snapshot_changed.emit(self.snapshot)

    def _fault_pointer_output(self, error: Exception) -> None:
        self._poll_timer.stop()
        released = False
        if self._dispatcher is not None:
            report = self._dispatcher.pause("pointer output failure")
            released = report.released
            self._emit_lifecycle(report)
        self._state = LiveInputState.FAULTED
        self._finish(
            False,
            f"Pointer output failed ({type(error).__name__}); Live Input was gated and "
            "tracking was paused.",
            released=released,
        )
        self.tracking_pause_requested.emit()

    def _schedule_next_poll(self) -> None:
        self._poll_timer.stop()
        if self._state is not LiveInputState.ARMED or self._dispatcher is None:
            return
        deadline = self._dispatcher.next_poll_deadline
        if deadline is None:
            return
        timestamp = self._safe_timestamp()
        if timestamp is None or self._state is not LiveInputState.ARMED:
            return
        delay_ms = max(1, ceil(max(0.0, deadline - timestamp) * 1000.0))
        self._poll_timer.start(min(delay_ms, _MAX_QT_TIMER_INTERVAL_MS))

    def _emit_lifecycle(self, report: LifecycleReport) -> None:
        self.lifecycle_finished.emit(report)

    def _finish(
        self,
        success: bool,
        message: str,
        released: bool = False,
    ) -> LiveInputResult:
        self._message = message
        result = LiveInputResult(success, self._state, message, released)
        self.lifecycle_finished.emit(result)
        self.snapshot_changed.emit(self.snapshot)
        return result


def _create_emergency_hotkey(parent: QObject) -> WindowsEmergencyHotkey:
    return WindowsEmergencyHotkey(parent=parent)
