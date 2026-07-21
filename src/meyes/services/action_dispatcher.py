"""Fail-safe, poll-driven execution of validated gesture bindings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Protocol, runtime_checkable

from meyes.bindings.manager import BindingManager, BindingPhase
from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.domain.actions import (
    Action,
    ContinuousScrollAction,
    DisabledAction,
    KeyboardKeyAction,
    KeyboardShortcutAction,
    MouseButton,
    MouseClickAction,
    MouseDoubleClickAction,
    MouseDownAction,
    MouseScrollAction,
    MouseUpAction,
    PauseTrackingAction,
    ResumeTrackingAction,
    ToggleTrackingAction,
)
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.input.interface import InputExecutor


class DispatcherState(StrEnum):
    """Safety gate for all action execution."""

    ACTIVE = "active"
    PAUSED = "paused"
    FAULTED = "faulted"
    CLOSED = "closed"


class DispatchStatus(StrEnum):
    """Outcome of one accepted event or scheduled continuous tick."""

    EXECUTED = "executed"
    DISABLED = "disabled"
    HOLD_STARTED = "hold_started"
    HOLD_ENDED = "hold_ended"
    CONTINUOUS_STARTED = "continuous_started"
    CONTINUOUS_TICK = "continuous_tick"
    DUPLICATE = "duplicate"
    STALE = "stale"
    INVALID = "invalid"
    INACTIVE = "inactive"
    ORPHAN_END = "orphan_end"
    RESOURCE_BUSY = "resource_busy"
    FAULTED = "faulted"
    REENTRANT_REJECTED = "reentrant_rejected"
    LIFECYCLE_REQUESTED = "lifecycle_requested"
    LIFECYCLE_UNAVAILABLE = "lifecycle_unavailable"


class _OrderingChannel(StrEnum):
    LEFT_WINK = "left_wink"
    RIGHT_WINK = "right_wink"
    LEFT_CHEEK = "left_cheek"
    RIGHT_CHEEK = "right_cheek"
    LEFT_TEMPLE = "left_temple"
    RIGHT_TEMPLE = "right_temple"


@dataclass(frozen=True, slots=True)
class DispatcherFault:
    """Stable diagnostic view of a contained runtime failure."""

    operation: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class DispatchReport:
    """Typed result returned without leaking executor exceptions."""

    status: DispatchStatus
    state: DispatcherState
    gesture: BindableGesture | None = None
    action_type: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class LifecycleReport:
    """Result of a safety lifecycle operation."""

    success: bool
    state: DispatcherState
    released: bool
    error: DispatcherFault | None = None


@dataclass(frozen=True, slots=True)
class DispatcherSnapshot:
    """Read-only dispatcher state for runtime diagnostics."""

    state: DispatcherState
    profile_name: str
    active_holds: tuple[BindableGesture, ...]
    next_poll_deadline: float | None
    fault: DispatcherFault | None


@runtime_checkable
class TrackingControl(Protocol):
    """Application lifecycle boundary kept separate from synthetic input."""

    def pause_tracking(self) -> None: ...

    def resume_tracking(self) -> None: ...


@dataclass(slots=True)
class _EventCursor:
    sequence: int
    event_types: set[GestureEventType]


@dataclass(slots=True)
class _HoldSession:
    gesture: BindableGesture
    start_sequence: int
    action: Action
    acquisition_order: int
    next_due: float | None = None


class _ExternalOutcome(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


_EVENT_ORDER: dict[GestureEventType, tuple[BindableGesture, _OrderingChannel]] = {
    GestureEventType.LEFT_WINK: (BindableGesture.LEFT_WINK, _OrderingChannel.LEFT_WINK),
    GestureEventType.RIGHT_WINK: (BindableGesture.RIGHT_WINK, _OrderingChannel.RIGHT_WINK),
    GestureEventType.LEFT_CHEEK_TOUCH: (
        BindableGesture.LEFT_CHEEK_TOUCH,
        _OrderingChannel.LEFT_CHEEK,
    ),
    GestureEventType.RIGHT_CHEEK_TOUCH: (
        BindableGesture.RIGHT_CHEEK_TOUCH,
        _OrderingChannel.RIGHT_CHEEK,
    ),
    GestureEventType.LEFT_TEMPLE_TAP: (
        BindableGesture.LEFT_TEMPLE_TAP,
        _OrderingChannel.LEFT_TEMPLE,
    ),
    GestureEventType.RIGHT_TEMPLE_TAP: (
        BindableGesture.RIGHT_TEMPLE_TAP,
        _OrderingChannel.RIGHT_TEMPLE,
    ),
    GestureEventType.LEFT_TEMPLE_HOLD_START: (
        BindableGesture.LEFT_TEMPLE_HOLD,
        _OrderingChannel.LEFT_TEMPLE,
    ),
    GestureEventType.LEFT_TEMPLE_HOLD_END: (
        BindableGesture.LEFT_TEMPLE_HOLD,
        _OrderingChannel.LEFT_TEMPLE,
    ),
    GestureEventType.RIGHT_TEMPLE_HOLD_START: (
        BindableGesture.RIGHT_TEMPLE_HOLD,
        _OrderingChannel.RIGHT_TEMPLE,
    ),
    GestureEventType.RIGHT_TEMPLE_HOLD_END: (
        BindableGesture.RIGHT_TEMPLE_HOLD,
        _OrderingChannel.RIGHT_TEMPLE,
    ),
}

_SAME_SEQUENCE_HOLD_ENDS = {
    GestureEventType.LEFT_TEMPLE_HOLD_END: GestureEventType.LEFT_TEMPLE_HOLD_START,
    GestureEventType.RIGHT_TEMPLE_HOLD_END: GestureEventType.RIGHT_TEMPLE_HOLD_START,
}
_TAP_HOLD_GESTURES = {
    GestureEventType.LEFT_TEMPLE_TAP: BindableGesture.LEFT_TEMPLE_HOLD,
    GestureEventType.RIGHT_TEMPLE_TAP: BindableGesture.RIGHT_TEMPLE_HOLD,
}

_RESUME_ACTIONS = (ResumeTrackingAction, ToggleTrackingAction)
_POLL_ORDER = {
    BindableGesture.LEFT_TEMPLE_HOLD: 0,
    BindableGesture.RIGHT_TEMPLE_HOLD: 1,
}


class ActionDispatcher:
    """Serialize bindings into safe fake/backend calls on one owning thread.

    The default state is deliberately paused. A runtime adapter must call
    :meth:`arm` only after its own tracking lifecycle is ready. This service owns
    a validated binding snapshot, contains backend errors, and never creates a
    timer or worker thread; callers drive continuous actions through :meth:`poll`.
    """

    def __init__(
        self,
        bindings: BindingManager,
        executor: InputExecutor,
        *,
        tracking_control: TrackingControl | None = None,
        safe_mode: bool = True,
    ) -> None:
        if not isinstance(bindings, BindingManager):
            raise TypeError("Expected BindingManager")
        if not isinstance(executor, InputExecutor):
            raise TypeError("Expected InputExecutor")
        if tracking_control is not None and not isinstance(tracking_control, TrackingControl):
            raise TypeError("Expected TrackingControl")
        if not isinstance(safe_mode, bool):
            raise TypeError("safe_mode must be a bool")
        self._bindings = BindingManager(bindings.active_profile)
        self._executor = executor
        self._tracking_control = tracking_control
        self._state = DispatcherState.PAUSED if safe_mode else DispatcherState.ACTIVE
        self._fault: DispatcherFault | None = None
        self._cursors: dict[_OrderingChannel, _EventCursor] = {}
        self._sessions: dict[BindableGesture, _HoldSession] = {}
        self._button_owners: dict[MouseButton, set[BindableGesture]] = {}
        self._last_timestamp: float | None = None
        self._acquisition_counter = 0
        self._generation = 0
        self._external_depth = 0
        self._releasing = False
        self._pausing_tracking = False
        self._pending_release = False
        self._fault_pause_pending = False

    @property
    def state(self) -> DispatcherState:
        """Return the current safety gate."""
        return self._state

    @property
    def fault(self) -> DispatcherFault | None:
        """Return the most recent contained failure, if any."""
        return self._fault

    @property
    def active_profile(self) -> BindingProfile:
        """Return an isolated copy of the dispatcher-owned profile."""
        return self._bindings.active_profile

    @property
    def active_holds(self) -> tuple[BindableGesture, ...]:
        """Return logical holds in deterministic acquisition order."""
        sessions = sorted(self._sessions.values(), key=lambda item: item.acquisition_order)
        return tuple(session.gesture for session in sessions)

    @property
    def next_poll_deadline(self) -> float | None:
        """Return the earliest continuous deadline without owning a timer."""
        deadlines = [
            session.next_due for session in self._sessions.values() if session.next_due is not None
        ]
        return min(deadlines) if deadlines else None

    @property
    def snapshot(self) -> DispatcherSnapshot:
        """Return an immutable diagnostic snapshot."""
        return DispatcherSnapshot(
            state=self._state,
            profile_name=self._bindings.active_profile.profile_name,
            active_holds=self.active_holds,
            next_poll_deadline=self.next_poll_deadline,
            fault=self._fault,
        )

    def dispatch(
        self,
        event: GestureEvent,
        *,
        current_timestamp: float,
    ) -> DispatchReport:
        """Validate, deduplicate, and attempt one semantic gesture event."""
        if not isinstance(event, GestureEvent):
            raise TypeError("Expected GestureEvent")
        validation_error = self._validate_event(event, current_timestamp)
        if validation_error is not None:
            return self._report(DispatchStatus.INVALID, detail=validation_error)
        now = float(current_timestamp)
        gesture, ordering_channel = _EVENT_ORDER[event.type]
        self._last_timestamp = now
        ordering_status = self._mark_event(event, ordering_channel)
        if ordering_status is not None:
            return self._report(ordering_status, gesture=gesture)
        if self._external_depth:
            self._enter_fault("reentrant_dispatch", RuntimeError("nested dispatch is unsafe"))
            self._drain_pending_release()
            return self._report(DispatchStatus.REENTRANT_REJECTED, gesture=gesture)
        active_hold = _TAP_HOLD_GESTURES.get(event.type)
        if active_hold in self._sessions:
            self._enter_fault(
                "temple_transition",
                RuntimeError("tap received while the same-side hold is active"),
            )
            self._drain_pending_release()
            return self._report(DispatchStatus.FAULTED, gesture=gesture)

        try:
            resolution = self._bindings.resolve(event)
        except Exception as error:
            self._enter_fault("binding_resolution", error)
            self._drain_pending_release()
            return self._report(DispatchStatus.FAULTED, gesture=gesture)

        if resolution.phase is BindingPhase.END:
            report = self._end_hold(resolution.gesture)
            self._drain_pending_release()
            return report

        action = resolution.action
        if action is None:
            self._enter_fault("binding_resolution", RuntimeError("missing start/trigger action"))
            self._drain_pending_release()
            return self._report(DispatchStatus.FAULTED, gesture=gesture)
        if self._state in {DispatcherState.FAULTED, DispatcherState.CLOSED}:
            return self._report(self._inactive_status(), gesture=gesture, action=action)
        if self._state is DispatcherState.PAUSED and not isinstance(action, _RESUME_ACTIONS):
            return self._report(DispatchStatus.INACTIVE, gesture=gesture, action=action)

        if resolution.phase is BindingPhase.START:
            report = self._start_hold(event, resolution.gesture, action, now)
        else:
            status = self._execute_action(action, gesture=None)
            report = self._report(status, gesture=resolution.gesture, action=action)
        self._drain_pending_release()
        return report

    def poll(self, timestamp: float) -> tuple[DispatchReport, ...]:
        """Attempt at most one due tick per continuous hold, with no catch-up."""
        validation_error = self._validate_clock(timestamp)
        if validation_error is not None:
            return (self._report(DispatchStatus.INVALID, detail=validation_error),)
        now = float(timestamp)
        self._last_timestamp = now
        if self._external_depth:
            self._enter_fault("reentrant_poll", RuntimeError("nested poll is unsafe"))
            self._drain_pending_release()
            return (self._report(DispatchStatus.REENTRANT_REJECTED),)
        if self._state is not DispatcherState.ACTIVE:
            return ()

        due = sorted(
            (
                session
                for session in self._sessions.values()
                if session.next_due is not None and session.next_due <= now
            ),
            key=lambda session: _POLL_ORDER[session.gesture],
        )
        reports: list[DispatchReport] = []
        for session in due:
            current = self._sessions.get(session.gesture)
            if current is not session or not isinstance(session.action, ContinuousScrollAction):
                continue
            next_due = _next_deadline(now, session.action.interval_ms)
            if next_due is None:
                self._enter_fault(
                    "continuous_schedule",
                    OverflowError("continuous deadline must be finite and advance time"),
                )
                reports.append(
                    self._report(
                        DispatchStatus.FAULTED,
                        gesture=session.gesture,
                        action=session.action,
                    )
                )
                break
            session.next_due = next_due
            outcome = self._call_external(
                "mouse_scroll_continuous",
                lambda amount=session.action.amount: self._executor.mouse_scroll(amount),
            )
            status = self._status_for_outcome(outcome, DispatchStatus.CONTINUOUS_TICK)
            reports.append(self._report(status, gesture=session.gesture, action=session.action))
            if outcome is not _ExternalOutcome.SUCCESS:
                break
        self._drain_pending_release()
        return tuple(reports)

    def pause(self, reason: str = "") -> LifecycleReport:
        """Gate dispatch and release every held primitive without resuming."""
        del reason
        if self._state is DispatcherState.CLOSED:
            return self._lifecycle_report(success=False, released=False)
        if self._external_depth:
            self._gate_and_defer_release(DispatcherState.PAUSED)
            return self._lifecycle_report(success=True, released=False)
        if self._state is not DispatcherState.FAULTED:
            self._state = DispatcherState.PAUSED
        self._generation += 1
        self._clear_sessions()
        self._pending_release = True
        released = self._perform_release()
        self._drain_pending_release()
        return self._lifecycle_report(success=released, released=released)

    def arm(self) -> LifecycleReport:
        """Preflight cleanup and explicitly enable action execution."""
        if self._state is not DispatcherState.PAUSED or self._external_depth:
            if self._external_depth:
                self._enter_fault("reentrant_arm", RuntimeError("arm during external call"))
            self._drain_pending_release()
            return self._lifecycle_report(success=False, released=False)
        self._generation += 1
        self._clear_sessions()
        self._pending_release = True
        released = self._perform_release()
        self._drain_pending_release()
        if released and self._state is DispatcherState.PAUSED:
            self._fault = None
            self._state = DispatcherState.ACTIVE
        return self._lifecycle_report(success=released, released=released)

    def recover(self) -> LifecycleReport:
        """Retry cleanup after a fault and land safely in PAUSED."""
        if self._state is not DispatcherState.FAULTED or self._external_depth:
            if self._external_depth:
                self._enter_fault("reentrant_recover", RuntimeError("recover during external call"))
            self._drain_pending_release()
            return self._lifecycle_report(success=False, released=False)
        self._generation += 1
        self._clear_sessions()
        self._pending_release = True
        released = self._perform_release()
        self._drain_pending_release()
        if released and self._state is DispatcherState.FAULTED:
            self._fault = None
            self._state = DispatcherState.PAUSED
        return self._lifecycle_report(success=released, released=released)

    def release_all(self, reason: str = "") -> LifecycleReport:
        """Clear logical ownership and release primitives without changing state."""
        del reason
        self._generation += 1
        self._clear_sessions()
        self._pending_release = True
        if self._external_depth:
            return self._lifecycle_report(success=True, released=False)
        released = self._perform_release()
        self._drain_pending_release()
        return self._lifecycle_report(success=released, released=released)

    def activate_profile(self, profile: BindingProfile) -> LifecycleReport:
        """Validate first, then quiesce before replacing the owned profile."""
        if not isinstance(profile, BindingProfile):
            raise TypeError("Expected BindingProfile")
        candidate = BindingManager(profile).active_profile
        if self._state in {DispatcherState.FAULTED, DispatcherState.CLOSED}:
            return self._lifecycle_report(success=False, released=False)
        if self._external_depth:
            self._enter_fault(
                "reentrant_profile_activation",
                RuntimeError("profile activation during external call"),
            )
            self._drain_pending_release()
            return self._lifecycle_report(success=False, released=False)
        self._state = DispatcherState.PAUSED
        self._generation += 1
        self._clear_sessions()
        self._pending_release = True
        released = self._perform_release()
        self._drain_pending_release()
        if not released:
            return self._lifecycle_report(success=False, released=False)
        try:
            self._bindings.activate(candidate)
        except Exception as error:
            self._enter_fault("profile_activation", error)
            self._drain_pending_release()
            return self._lifecycle_report(success=False, released=True)
        return self._lifecycle_report(success=True, released=True)

    def begin_event_epoch(self) -> LifecycleReport:
        """Reset producer ordering only while paused and after cleanup."""
        if self._state is not DispatcherState.PAUSED or self._external_depth:
            if self._external_depth:
                self._enter_fault(
                    "reentrant_epoch", RuntimeError("epoch reset during external call")
                )
            self._drain_pending_release()
            return self._lifecycle_report(success=False, released=False)
        self._generation += 1
        self._clear_sessions()
        self._pending_release = True
        released = self._perform_release()
        self._drain_pending_release()
        if released and self._state is DispatcherState.PAUSED:
            self._cursors.clear()
            self._last_timestamp = None
        return self._lifecycle_report(success=released, released=released)

    def close(self) -> LifecycleReport:
        """Enter the terminal state first, then best-effort release all input."""
        self._state = DispatcherState.CLOSED
        self._generation += 1
        self._clear_sessions()
        self._pending_release = True
        if self._external_depth:
            return self._lifecycle_report(success=True, released=False)
        released = self._perform_release()
        self._drain_pending_release()
        return self._lifecycle_report(success=released, released=released)

    def _start_hold(
        self,
        event: GestureEvent,
        gesture: BindableGesture,
        action: Action,
        now: float,
    ) -> DispatchReport:
        if gesture in self._sessions:
            self._enter_fault("hold_transition", RuntimeError("hold started while already active"))
            return self._report(DispatchStatus.FAULTED, gesture=gesture, action=action)
        self._acquisition_counter += 1
        next_due = None
        if isinstance(action, ContinuousScrollAction):
            next_due = _next_deadline(now, action.interval_ms)
            if next_due is None:
                self._enter_fault(
                    "continuous_schedule",
                    OverflowError("continuous deadline must be finite and advance time"),
                )
                return self._report(DispatchStatus.FAULTED, gesture=gesture, action=action)
        self._sessions[gesture] = _HoldSession(
            gesture=gesture,
            start_sequence=event.source_sequence,
            action=action,
            acquisition_order=self._acquisition_counter,
            next_due=next_due,
        )
        if isinstance(action, ContinuousScrollAction):
            return self._report(DispatchStatus.CONTINUOUS_STARTED, gesture=gesture, action=action)
        status = self._execute_action(action, gesture=gesture)
        return self._report(status, gesture=gesture, action=action)

    def _end_hold(self, gesture: BindableGesture) -> DispatchReport:
        session = self._sessions.pop(gesture, None)
        if session is None:
            return self._report(DispatchStatus.ORPHAN_END, gesture=gesture)
        action = session.action
        if not isinstance(action, MouseDownAction):
            return self._report(DispatchStatus.HOLD_ENDED, gesture=gesture, action=action)
        owners = self._button_owners.get(action.button)
        if owners is None:
            self._enter_fault("mouse_ownership", RuntimeError("missing mouse button owner"))
            return self._report(DispatchStatus.FAULTED, gesture=gesture, action=action)
        owners.discard(gesture)
        if owners:
            return self._report(DispatchStatus.HOLD_ENDED, gesture=gesture, action=action)
        del self._button_owners[action.button]
        outcome = self._call_external(
            "mouse_up_hold_end",
            lambda: self._executor.mouse_up(action.button),
        )
        status = self._status_for_outcome(outcome, DispatchStatus.HOLD_ENDED)
        return self._report(status, gesture=gesture, action=action)

    def _execute_action(
        self,
        action: Action,
        *,
        gesture: BindableGesture | None,
    ) -> DispatchStatus:
        if isinstance(action, DisabledAction):
            return DispatchStatus.DISABLED
        if isinstance(action, MouseClickAction):
            if self._button_owners.get(action.button):
                return DispatchStatus.RESOURCE_BUSY
            outcome = self._call_external(
                "mouse_click",
                lambda: self._executor.mouse_click(action.button),
            )
            return self._status_for_outcome(outcome)
        if isinstance(action, MouseDoubleClickAction):
            if self._button_owners.get(action.button):
                return DispatchStatus.RESOURCE_BUSY
            for index in range(2):
                outcome = self._call_external(
                    f"mouse_double_click_{index + 1}",
                    lambda: self._executor.mouse_click(action.button),
                )
                if outcome is not _ExternalOutcome.SUCCESS:
                    return self._status_for_outcome(outcome)
            return DispatchStatus.EXECUTED
        if isinstance(action, MouseDownAction):
            if gesture is None:
                self._enter_fault("mouse_down", RuntimeError("mouse down requires hold owner"))
                return DispatchStatus.FAULTED
            owners = self._button_owners.setdefault(action.button, set())
            is_first_owner = not owners
            owners.add(gesture)
            if not is_first_owner:
                return DispatchStatus.HOLD_STARTED
            outcome = self._call_external(
                "mouse_down",
                lambda: self._executor.mouse_down(action.button),
            )
            return self._status_for_outcome(outcome, DispatchStatus.HOLD_STARTED)
        if isinstance(action, MouseUpAction):
            self._cancel_button_owners(action)
            outcome = self._call_external(
                "mouse_up",
                lambda: self._executor.mouse_up(action.button),
            )
            return self._status_for_outcome(outcome)
        if isinstance(action, MouseScrollAction):
            outcome = self._call_external(
                "mouse_scroll",
                lambda: self._executor.mouse_scroll(action.amount),
            )
            return self._status_for_outcome(outcome)
        if isinstance(action, ContinuousScrollAction):
            self._enter_fault(
                "continuous_scroll",
                RuntimeError("continuous scroll requires a hold start"),
            )
            return DispatchStatus.FAULTED
        if isinstance(action, KeyboardKeyAction):
            outcome = self._call_external(
                "keyboard_key",
                lambda: self._tap_key(action),
            )
            return self._status_for_outcome(outcome)
        if isinstance(action, KeyboardShortcutAction):
            outcome = self._call_external(
                "keyboard_shortcut",
                lambda: self._executor.keyboard_shortcut(action.keys),
            )
            return self._status_for_outcome(outcome)
        if isinstance(action, PauseTrackingAction):
            return self._request_tracking(enabled=False)
        if isinstance(action, ResumeTrackingAction):
            return self._request_tracking(enabled=True)
        if isinstance(action, ToggleTrackingAction):
            return self._request_tracking(enabled=self._state is not DispatcherState.ACTIVE)

    def _request_tracking(self, *, enabled: bool) -> DispatchStatus:
        if self._state is DispatcherState.CLOSED:
            return DispatchStatus.INACTIVE
        self._state = DispatcherState.PAUSED
        self._generation += 1
        self._clear_sessions()
        self._pending_release = True
        released = self._perform_release()
        callback = None
        operation = "resume_tracking" if enabled else "pause_tracking"
        if self._tracking_control is not None:
            callback = (
                self._tracking_control.resume_tracking
                if enabled
                else self._tracking_control.pause_tracking
            )
        if callback is None:
            self._drain_pending_release()
            return (
                DispatchStatus.FAULTED
                if self._state is DispatcherState.FAULTED
                else DispatchStatus.LIFECYCLE_UNAVAILABLE
            )
        if enabled and not released:
            self._drain_pending_release()
            return DispatchStatus.FAULTED
        if not enabled:
            self._fault_pause_pending = False
        outcome = self._call_external(operation, callback)
        if self._state is DispatcherState.FAULTED:
            return DispatchStatus.FAULTED
        return self._status_for_outcome(outcome, DispatchStatus.LIFECYCLE_REQUESTED)

    def _tap_key(self, action: KeyboardKeyAction) -> None:
        errors: list[Exception] = []
        try:
            self._executor.key_down(action.key)
        except Exception as error:
            errors.append(error)
        try:
            self._executor.key_up(action.key)
        except Exception as error:
            errors.append(error)
        if errors:
            details = "; ".join(f"{type(error).__name__}: {error}" for error in errors)
            raise RuntimeError(f"key tap failed: {details}")

    def _cancel_button_owners(self, action: MouseUpAction) -> None:
        owners = self._button_owners.pop(action.button, set())
        for owner in owners:
            session = self._sessions.get(owner)
            if (
                session is not None
                and isinstance(session.action, MouseDownAction)
                and session.action.button is action.button
            ):
                del self._sessions[owner]

    def _validate_event(self, event: GestureEvent, timestamp: object) -> str | None:
        event_type: object = event.type
        if not isinstance(event_type, GestureEventType):
            return "event type must be GestureEventType"
        if isinstance(event.source_sequence, bool) or not isinstance(event.source_sequence, int):
            return "source sequence must be a nonnegative integer"
        if event.source_sequence < 0:
            return "source sequence must be a nonnegative integer"
        event_timestamp_error = _finite_nonnegative(event.timestamp, "event timestamp")
        if event_timestamp_error is not None:
            return event_timestamp_error
        duration_error = _finite_nonnegative(event.duration_ms, "event duration")
        if duration_error is not None:
            return duration_error
        clock_error = self._validate_clock(timestamp)
        if clock_error is not None:
            return clock_error
        assert isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool)
        if float(event.timestamp) > float(timestamp):
            return "event timestamp must not be in the future"
        return None

    def _validate_clock(self, timestamp: object) -> str | None:
        error = _finite_nonnegative(timestamp, "dispatcher timestamp")
        if error is not None:
            return error
        assert isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool)
        if self._last_timestamp is not None and float(timestamp) < self._last_timestamp:
            return "dispatcher timestamp must be monotonic"
        return None

    def _mark_event(
        self,
        event: GestureEvent,
        channel: _OrderingChannel,
    ) -> DispatchStatus | None:
        cursor = self._cursors.get(channel)
        if cursor is None or event.source_sequence > cursor.sequence:
            self._cursors[channel] = _EventCursor(
                sequence=event.source_sequence,
                event_types={event.type},
            )
            return None
        if event.source_sequence < cursor.sequence:
            return DispatchStatus.STALE
        if event.type in cursor.event_types:
            return DispatchStatus.DUPLICATE
        required_start = _SAME_SEQUENCE_HOLD_ENDS.get(event.type)
        if required_start is None or required_start not in cursor.event_types:
            return DispatchStatus.STALE
        cursor.event_types.add(event.type)
        return None

    def _call_external(self, operation: str, callback: object) -> _ExternalOutcome:
        if not callable(callback):
            self._enter_fault(operation, TypeError("external callback is not callable"))
            return _ExternalOutcome.FAILED
        if self._external_depth:
            self._enter_fault(operation, RuntimeError("nested external call is unsafe"))
            return _ExternalOutcome.FAILED
        generation = self._generation
        self._external_depth += 1
        failed = False
        try:
            callback()
        except Exception as error:
            failed = True
            self._enter_fault(operation, error)
        finally:
            self._external_depth -= 1
        self._drain_pending_release()
        if failed:
            return _ExternalOutcome.FAILED
        if generation != self._generation:
            return _ExternalOutcome.INTERRUPTED
        return _ExternalOutcome.SUCCESS

    def _enter_fault(self, operation: str, error: Exception) -> None:
        if self._state is not DispatcherState.CLOSED:
            self._state = DispatcherState.FAULTED
        self._fault = DispatcherFault(
            operation=operation,
            error_type=type(error).__name__,
            message=str(error),
        )
        self._generation += 1
        self._clear_sessions()
        self._pending_release = True
        if (
            self._tracking_control is not None
            and operation != "pause_tracking"
            and not self._pausing_tracking
        ):
            self._fault_pause_pending = True

    def _gate_and_defer_release(self, state: DispatcherState) -> None:
        if self._state not in {DispatcherState.CLOSED, DispatcherState.FAULTED}:
            self._state = state
        self._generation += 1
        self._clear_sessions()
        self._pending_release = True

    def _drain_pending_release(self) -> None:
        if self._external_depth or self._releasing or self._pausing_tracking:
            return
        if self._pending_release:
            self._perform_release()
        pause_attempted = False
        if self._fault_pause_pending:
            self._fault_pause_pending = False
            self._perform_fault_pause()
            pause_attempted = True
        if self._pending_release:
            self._perform_release()
            if pause_attempted:
                self._fault_pause_pending = False

    def _perform_fault_pause(self) -> None:
        control = self._tracking_control
        if control is None or self._external_depth or self._pausing_tracking:
            return
        self._pausing_tracking = True
        self._external_depth += 1
        pause_error: Exception | None = None
        try:
            control.pause_tracking()
        except Exception as error:
            pause_error = error
        finally:
            self._external_depth -= 1
            self._pausing_tracking = False
        if pause_error is not None:
            if self._state is not DispatcherState.CLOSED:
                self._state = DispatcherState.FAULTED
            self._fault = DispatcherFault(
                operation="fault_pause_tracking",
                error_type=type(pause_error).__name__,
                message=str(pause_error),
            )
            self._generation += 1
            self._clear_sessions()
            self._pending_release = True

    def _perform_release(self) -> bool:
        if self._releasing or self._external_depth:
            self._pending_release = True
            return False
        self._pending_release = False
        self._releasing = True
        self._external_depth += 1
        release_error: Exception | None = None
        try:
            self._executor.release_all()
        except Exception as error:
            release_error = error
        finally:
            self._external_depth -= 1
            self._releasing = False
        interrupted = self._pending_release
        if release_error is not None:
            if self._state is not DispatcherState.CLOSED:
                self._state = DispatcherState.FAULTED
            self._fault = DispatcherFault(
                operation="release_all",
                error_type=type(release_error).__name__,
                message=str(release_error),
            )
            self._generation += 1
            self._clear_sessions()
            self._pending_release = False
            if self._tracking_control is not None and not self._pausing_tracking:
                self._fault_pause_pending = True
            return False
        self._pending_release = False
        return not interrupted

    def _clear_sessions(self) -> None:
        self._sessions.clear()
        self._button_owners.clear()

    def _status_for_outcome(
        self,
        outcome: _ExternalOutcome,
        success: DispatchStatus = DispatchStatus.EXECUTED,
    ) -> DispatchStatus:
        if outcome is _ExternalOutcome.SUCCESS:
            return success
        if self._state is DispatcherState.FAULTED:
            return DispatchStatus.FAULTED
        return DispatchStatus.INACTIVE

    def _inactive_status(self) -> DispatchStatus:
        if self._state is DispatcherState.FAULTED:
            return DispatchStatus.FAULTED
        return DispatchStatus.INACTIVE

    def _report(
        self,
        status: DispatchStatus,
        *,
        gesture: BindableGesture | None = None,
        action: Action | None = None,
        detail: str | None = None,
    ) -> DispatchReport:
        return DispatchReport(
            status=status,
            state=self._state,
            gesture=gesture,
            action_type=action.type if action is not None else None,
            detail=detail,
        )

    def _lifecycle_report(self, *, success: bool, released: bool) -> LifecycleReport:
        return LifecycleReport(
            success=success,
            state=self._state,
            released=released,
            error=self._fault if not success else None,
        )


def _finite_nonnegative(value: object, label: str) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"{label} must be a finite nonnegative number"
    try:
        normalized = float(value)
    except (OverflowError, TypeError, ValueError):
        return f"{label} must be a finite nonnegative number"
    if not isfinite(normalized) or normalized < 0:
        return f"{label} must be a finite nonnegative number"
    return None


def _next_deadline(now: float, interval_ms: int) -> float | None:
    deadline = now + (interval_ms / 1000.0)
    if not isfinite(deadline) or deadline <= now:
        return None
    return deadline
