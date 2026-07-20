"""Dormant cursor movement gate tests."""

from __future__ import annotations

import pytest

from meyes.cursor.gate import CursorGateSettings, CursorGateState, CursorMovementGate, TempleSide
from meyes.domain.events import GestureEvent, GestureEventType


def event(kind: GestureEventType, timestamp: float, sequence: int) -> GestureEvent:
    return GestureEvent(kind, timestamp, sequence, 100.0)


def open_gate(gate: CursorMovementGate) -> None:
    assert gate.snapshot.state is CursorGateState.SUSPENDED
    gate.resume_tracking(1.0)
    assert gate.poll(1.12).state is CursorGateState.OPEN


def test_gate_starts_suspended_and_resumes_only_after_delay() -> None:
    gate = CursorMovementGate()

    resumed = gate.resume_tracking(1.0)

    assert resumed.state is CursorGateState.RESUME_DELAY
    assert not resumed.movement_allowed
    assert gate.poll(1.119).state is CursorGateState.RESUME_DELAY
    assert gate.poll(1.12).movement_allowed


def test_overlapping_holds_require_both_sides_to_end() -> None:
    gate = CursorMovementGate()
    open_gate(gate)

    left = gate.handle_event(event(GestureEventType.LEFT_TEMPLE_HOLD_START, 1.2, 1))
    both = gate.handle_event(event(GestureEventType.RIGHT_TEMPLE_HOLD_START, 1.3, 2))
    one_left = gate.handle_event(event(GestureEventType.LEFT_TEMPLE_HOLD_END, 1.4, 3))
    ended = gate.handle_event(event(GestureEventType.RIGHT_TEMPLE_HOLD_END, 1.5, 4))

    assert left.active_holds == (TempleSide.LEFT,)
    assert both.active_holds == (TempleSide.LEFT, TempleSide.RIGHT)
    assert one_left.state is CursorGateState.TEMPLE_FROZEN
    assert ended.state is CursorGateState.RESUME_DELAY
    assert gate.poll(1.62).state is CursorGateState.OPEN


def test_tap_creates_resume_delay_pulse() -> None:
    gate = CursorMovementGate()
    open_gate(gate)

    tapped = gate.handle_event(event(GestureEventType.LEFT_TEMPLE_TAP, 1.3, 1))

    assert tapped.state is CursorGateState.RESUME_DELAY
    assert gate.poll(1.419).state is CursorGateState.RESUME_DELAY
    assert gate.poll(1.42).state is CursorGateState.OPEN


def test_tracking_loss_wins_and_clears_holds() -> None:
    gate = CursorMovementGate()
    open_gate(gate)
    gate.handle_event(event(GestureEventType.LEFT_TEMPLE_HOLD_START, 1.3, 1))

    suspended = gate.suspend(1.4)

    assert suspended.state is CursorGateState.SUSPENDED
    assert suspended.active_holds == ()
    assert not gate.poll(10.0).movement_allowed


def test_disabled_temple_freeze_never_disables_tracking_safety() -> None:
    gate = CursorMovementGate(CursorGateSettings(False, 0.12))
    gate.resume_tracking(1.0)
    assert gate.snapshot.state is CursorGateState.OPEN

    assert gate.handle_event(
        event(GestureEventType.LEFT_TEMPLE_HOLD_START, 1.1, 1)
    ).movement_allowed
    assert gate.suspend(1.2).state is CursorGateState.SUSPENDED


def test_duplicate_event_is_idempotent_and_ordering_fails_closed() -> None:
    gate = CursorMovementGate()
    open_gate(gate)
    started = event(GestureEventType.LEFT_TEMPLE_HOLD_START, 1.3, 2)
    gate.handle_event(started)

    assert gate.handle_event(started).active_holds == (TempleSide.LEFT,)
    with pytest.raises(ValueError, match="timestamps"):
        gate.handle_event(event(GestureEventType.LEFT_TEMPLE_HOLD_END, 1.2, 3))
    with pytest.raises(ValueError, match="sequences"):
        gate.handle_event(event(GestureEventType.LEFT_TEMPLE_HOLD_END, 1.4, 1))


def test_reset_requires_fresh_tracking_resume() -> None:
    gate = CursorMovementGate()
    open_gate(gate)

    assert gate.reset().state is CursorGateState.SUSPENDED
    assert not gate.snapshot.movement_allowed
