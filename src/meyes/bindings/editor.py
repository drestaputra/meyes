"""Typed text codec for the no-execution binding draft editor."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import ValidationError

from meyes.bindings.models import HOLD_GESTURES, BindableGesture
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


class EditableActionKind(StrEnum):
    """Stable action choices exposed by the draft editor."""

    DISABLED = "disabled"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DOUBLE_CLICK = "mouse_double_click"
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    MOUSE_SCROLL = "mouse_scroll"
    CONTINUOUS_SCROLL = "mouse_scroll_continuous"
    KEYBOARD_KEY = "keyboard_key"
    KEYBOARD_SHORTCUT = "keyboard_shortcut"
    PAUSE_TRACKING = "pause_tracking"
    RESUME_TRACKING = "resume_tracking"
    TOGGLE_TRACKING = "toggle_tracking"


ACTION_KIND_ORDER = tuple(EditableActionKind)
_HOLD_ONLY_KINDS = frozenset({EditableActionKind.MOUSE_DOWN, EditableActionKind.CONTINUOUS_SCROLL})
_ACTION_LABELS = {
    EditableActionKind.DISABLED: "Disabled",
    EditableActionKind.MOUSE_CLICK: "Mouse click",
    EditableActionKind.MOUSE_DOUBLE_CLICK: "Mouse double-click",
    EditableActionKind.MOUSE_DOWN: "Hold mouse button",
    EditableActionKind.MOUSE_UP: "Release mouse button",
    EditableActionKind.MOUSE_SCROLL: "Mouse scroll",
    EditableActionKind.CONTINUOUS_SCROLL: "Continuous scroll",
    EditableActionKind.KEYBOARD_KEY: "Keyboard key",
    EditableActionKind.KEYBOARD_SHORTCUT: "Keyboard shortcut",
    EditableActionKind.PAUSE_TRACKING: "Pause tracking",
    EditableActionKind.RESUME_TRACKING: "Resume tracking",
    EditableActionKind.TOGGLE_TRACKING: "Toggle tracking",
}
_PARAMETER_HINTS = {
    EditableActionKind.DISABLED: "No parameters",
    EditableActionKind.MOUSE_CLICK: "left, right, or middle",
    EditableActionKind.MOUSE_DOUBLE_CLICK: "left, right, or middle",
    EditableActionKind.MOUSE_DOWN: "left, right, or middle",
    EditableActionKind.MOUSE_UP: "left, right, or middle",
    EditableActionKind.MOUSE_SCROLL: "non-zero steps (-20 to 20)",
    EditableActionKind.CONTINUOUS_SCROLL: "amount, interval ms (for example -2, 100)",
    EditableActionKind.KEYBOARD_KEY: "key name (for example ENTER or F6)",
    EditableActionKind.KEYBOARD_SHORTCUT: "keys joined by + (for example CTRL + SHIFT + A)",
    EditableActionKind.PAUSE_TRACKING: "No parameters",
    EditableActionKind.RESUME_TRACKING: "No parameters",
    EditableActionKind.TOGGLE_TRACKING: "No parameters",
}
_PARAMETERLESS_KINDS = frozenset(
    {
        EditableActionKind.DISABLED,
        EditableActionKind.PAUSE_TRACKING,
        EditableActionKind.RESUME_TRACKING,
        EditableActionKind.TOGGLE_TRACKING,
    }
)
_BUTTON_KINDS = frozenset(
    {
        EditableActionKind.MOUSE_CLICK,
        EditableActionKind.MOUSE_DOUBLE_CLICK,
        EditableActionKind.MOUSE_DOWN,
        EditableActionKind.MOUSE_UP,
    }
)
_INTEGER_PATTERN = re.compile(r"[+-]?\d+")
_MAX_PARAMETER_CHARACTERS = 200


def editable_action_kinds(gesture: BindableGesture) -> tuple[EditableActionKind, ...]:
    """Return editor choices that can produce a valid binding for one gesture."""
    if not isinstance(gesture, BindableGesture):
        raise TypeError("Expected BindableGesture")
    if gesture in HOLD_GESTURES:
        return ACTION_KIND_ORDER
    return tuple(kind for kind in ACTION_KIND_ORDER if kind not in _HOLD_ONLY_KINDS)


def action_kind_label(kind: EditableActionKind) -> str:
    """Return a stable user-facing action choice label."""
    if not isinstance(kind, EditableActionKind):
        raise TypeError("Expected EditableActionKind")
    return _ACTION_LABELS[kind]


def action_parameter_hint(kind: EditableActionKind) -> str:
    """Return plain-language parameter guidance for one action kind."""
    if not isinstance(kind, EditableActionKind):
        raise TypeError("Expected EditableActionKind")
    return _PARAMETER_HINTS[kind]


def action_accepts_parameters(kind: EditableActionKind) -> bool:
    """Report whether the action kind accepts a parameter string."""
    if not isinstance(kind, EditableActionKind):
        raise TypeError("Expected EditableActionKind")
    return kind not in _PARAMETERLESS_KINDS


def action_kind_for(action: Action) -> EditableActionKind:
    """Return the editor kind for a validated action model."""
    if isinstance(action, DisabledAction):
        return EditableActionKind.DISABLED
    if isinstance(action, MouseClickAction):
        return EditableActionKind.MOUSE_CLICK
    if isinstance(action, MouseDoubleClickAction):
        return EditableActionKind.MOUSE_DOUBLE_CLICK
    if isinstance(action, MouseDownAction):
        return EditableActionKind.MOUSE_DOWN
    if isinstance(action, MouseUpAction):
        return EditableActionKind.MOUSE_UP
    if isinstance(action, MouseScrollAction):
        return EditableActionKind.MOUSE_SCROLL
    if isinstance(action, ContinuousScrollAction):
        return EditableActionKind.CONTINUOUS_SCROLL
    if isinstance(action, KeyboardKeyAction):
        return EditableActionKind.KEYBOARD_KEY
    if isinstance(action, KeyboardShortcutAction):
        return EditableActionKind.KEYBOARD_SHORTCUT
    if isinstance(action, PauseTrackingAction):
        return EditableActionKind.PAUSE_TRACKING
    if isinstance(action, ResumeTrackingAction):
        return EditableActionKind.RESUME_TRACKING
    if isinstance(action, ToggleTrackingAction):
        return EditableActionKind.TOGGLE_TRACKING
    raise TypeError("Expected supported action")


def format_action_parameters(action: Action) -> str:
    """Serialize action parameters into the editor's reversible text grammar."""
    if isinstance(
        action,
        (DisabledAction, PauseTrackingAction, ResumeTrackingAction, ToggleTrackingAction),
    ):
        return ""
    if isinstance(
        action,
        (MouseClickAction, MouseDoubleClickAction, MouseDownAction, MouseUpAction),
    ):
        return action.button.value
    if isinstance(action, MouseScrollAction):
        return str(action.amount)
    if isinstance(action, ContinuousScrollAction):
        return f"{action.amount}, {action.interval_ms}"
    if isinstance(action, KeyboardKeyAction):
        return action.key.value
    if isinstance(action, KeyboardShortcutAction):
        return " + ".join(key.value for key in action.keys)
    raise TypeError("Expected supported action")


def parse_action(
    gesture: BindableGesture,
    kind: EditableActionKind,
    parameters: str,
) -> Action:
    """Parse one editor row without executing or persisting the result."""
    if not isinstance(gesture, BindableGesture):
        raise TypeError("Expected BindableGesture")
    if not isinstance(kind, EditableActionKind):
        raise TypeError("Expected EditableActionKind")
    if not isinstance(parameters, str):
        raise TypeError("parameters must be a string")
    if len(parameters) > _MAX_PARAMETER_CHARACTERS:
        raise ValueError("Parameters must contain at most 200 characters.")
    if kind not in editable_action_kinds(gesture):
        raise ValueError("This action is available only for temple hold gestures.")
    normalized = parameters.strip()
    if kind in _PARAMETERLESS_KINDS:
        if normalized:
            raise ValueError("Remove parameters for this action.")
        return _parameterless_action(kind)
    if kind in _BUTTON_KINDS:
        return _button_action(kind, normalized)
    if kind is EditableActionKind.MOUSE_SCROLL:
        amount = _parse_integer(normalized, "Enter a non-zero whole number from -20 to 20.")
        try:
            return MouseScrollAction(amount=amount)
        except ValidationError as error:
            raise ValueError("Enter a non-zero whole number from -20 to 20.") from error
    if kind is EditableActionKind.CONTINUOUS_SCROLL:
        return _continuous_scroll_action(normalized)
    if kind is EditableActionKind.KEYBOARD_KEY:
        try:
            return KeyboardKeyAction(key=normalized)
        except (ValidationError, ValueError) as error:
            raise ValueError("Use a supported key name such as ENTER, A, or F6.") from error
    if kind is EditableActionKind.KEYBOARD_SHORTCUT:
        parts = tuple(part.strip() for part in normalized.split("+"))
        if not normalized or any(not part for part in parts):
            raise ValueError("Use modifiers plus one key, for example CTRL + SHIFT + A.")
        try:
            return KeyboardShortcutAction(keys=parts)
        except (ValidationError, ValueError) as error:
            raise ValueError(
                "Use unique modifiers followed by one key, for example CTRL + SHIFT + A."
            ) from error
    raise AssertionError("Unhandled editable action kind")


def _parameterless_action(kind: EditableActionKind) -> Action:
    if kind is EditableActionKind.DISABLED:
        return DisabledAction()
    if kind is EditableActionKind.PAUSE_TRACKING:
        return PauseTrackingAction()
    if kind is EditableActionKind.RESUME_TRACKING:
        return ResumeTrackingAction()
    if kind is EditableActionKind.TOGGLE_TRACKING:
        return ToggleTrackingAction()
    raise AssertionError("Action kind requires parameters")


def _button_action(kind: EditableActionKind, value: str) -> Action:
    try:
        button = MouseButton(value.casefold())
    except ValueError as error:
        raise ValueError("Use left, right, or middle.") from error
    if kind is EditableActionKind.MOUSE_CLICK:
        return MouseClickAction(button=button)
    if kind is EditableActionKind.MOUSE_DOUBLE_CLICK:
        return MouseDoubleClickAction(button=button)
    if kind is EditableActionKind.MOUSE_DOWN:
        return MouseDownAction(button=button)
    if kind is EditableActionKind.MOUSE_UP:
        return MouseUpAction(button=button)
    raise AssertionError("Action kind is not a mouse-button action")


def _continuous_scroll_action(value: str) -> ContinuousScrollAction:
    parts = tuple(part.strip() for part in value.split(","))
    message = "Enter amount and interval as amount, milliseconds (for example: -2, 100)."
    if len(parts) != 2:
        raise ValueError(message)
    amount = _parse_integer(parts[0], message)
    interval_ms = _parse_integer(parts[1], message)
    try:
        return ContinuousScrollAction(amount=amount, interval_ms=interval_ms)
    except ValidationError as error:
        raise ValueError("Use non-zero amount -20 to 20 and interval 25 to 5000 ms.") from error


def _parse_integer(value: str, message: str) -> int:
    if not _INTEGER_PATTERN.fullmatch(value):
        raise ValueError(message)
    return int(value)
