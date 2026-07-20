"""Validation tests for the closed MVP action vocabulary."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from meyes.domain.actions import (
    Action,
    ContinuousScrollAction,
    DisabledAction,
    KeyboardKeyAction,
    KeyboardShortcutAction,
    KeyName,
    MouseButton,
    MouseClickAction,
    MouseScrollAction,
)

ACTION_ADAPTER: TypeAdapter[Action] = TypeAdapter(Action)


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "disabled"},
        {"type": "mouse_click", "button": "left"},
        {"type": "mouse_double_click", "button": "right"},
        {"type": "mouse_down", "button": "middle"},
        {"type": "mouse_up", "button": "left"},
        {"type": "mouse_scroll", "amount": -3},
        {"type": "mouse_scroll_continuous", "amount": 2, "interval_ms": 100},
        {"type": "keyboard_key", "key": "A"},
        {"type": "keyboard_shortcut", "keys": ["CTRL", "SHIFT", "TAB"]},
        {"type": "pause_tracking"},
        {"type": "resume_tracking"},
        {"type": "toggle_tracking"},
    ],
)
def test_every_supported_action_round_trips_through_discriminator(payload: dict[str, Any]) -> None:
    action = ACTION_ADAPTER.validate_python(payload)

    serialized = ACTION_ADAPTER.dump_python(action, mode="json")

    assert serialized == payload
    assert ACTION_ADAPTER.validate_python(serialized) == action


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "shell_command", "command": "whoami"},
        {"type": "disabled", "command": "whoami"},
        {"type": "mouse_click", "button": "back"},
        {"type": "mouse_scroll", "amount": 0},
        {"type": "mouse_scroll", "amount": 21},
        {"type": "mouse_scroll", "amount": "3"},
        {"type": "mouse_scroll_continuous", "amount": 2, "interval_ms": 24},
        {"type": "mouse_scroll_continuous", "amount": 2, "interval_ms": 5001},
        {"type": "mouse_scroll_continuous", "amount": 2, "interval_ms": True},
    ],
)
def test_unsupported_or_unsafe_actions_are_rejected(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(payload)


def test_key_names_are_normalized_but_unknown_aliases_are_rejected() -> None:
    assert KeyboardKeyAction(key=" f12 ").key is KeyName.F12

    with pytest.raises(ValidationError, match="key"):
        KeyboardKeyAction(key="CONTROL")


def test_shortcut_is_normalized_and_immutable() -> None:
    action = KeyboardShortcutAction(keys=[" ctrl ", "shift", "tab"])

    assert action.keys == (KeyName.CTRL, KeyName.SHIFT, KeyName.TAB)
    with pytest.raises(ValidationError, match="frozen"):
        action.keys = (KeyName.A,)  # type: ignore[misc]


@pytest.mark.parametrize(
    "keys",
    [
        [],
        ["CTRL"],
        ["CTRL", "ALT"],
        ["A", "B"],
        ["A", "CTRL"],
        ["CTRL", "A", "a"],
        ["CTRL", "ALT", "SHIFT", "WIN", "A", "F1"],
        "CTRL+A",
    ],
)
def test_invalid_shortcut_chords_are_rejected(keys: object) -> None:
    with pytest.raises(ValidationError):
        KeyboardShortcutAction(keys=keys)


def test_typed_action_constructors_keep_expected_values() -> None:
    assert DisabledAction().type == "disabled"
    assert MouseClickAction(button=MouseButton.LEFT).button is MouseButton.LEFT
    assert MouseScrollAction(amount=-20).amount == -20
    assert ContinuousScrollAction(amount=20, interval_ms=5000).interval_ms == 5000
