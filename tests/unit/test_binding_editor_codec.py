"""No-execution binding editor codec tests."""

from __future__ import annotations

import pytest

from meyes.bindings.editor import (
    EditableActionKind,
    action_accepts_parameters,
    action_kind_for,
    action_kind_label,
    action_parameter_hint,
    editable_action_kinds,
    format_action_parameters,
    parse_action,
)
from meyes.bindings.models import BindableGesture
from meyes.domain.actions import (
    Action,
    ContinuousScrollAction,
    DisabledAction,
    KeyboardKeyAction,
    KeyboardShortcutAction,
    KeyName,
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


@pytest.mark.parametrize(
    ("gesture", "action"),
    [
        (BindableGesture.LEFT_WINK, DisabledAction()),
        (BindableGesture.LEFT_WINK, MouseClickAction(button=MouseButton.LEFT)),
        (BindableGesture.RIGHT_WINK, MouseDoubleClickAction(button=MouseButton.RIGHT)),
        (BindableGesture.LEFT_TEMPLE_HOLD, MouseDownAction(button=MouseButton.MIDDLE)),
        (BindableGesture.LEFT_WINK, MouseUpAction(button=MouseButton.LEFT)),
        (BindableGesture.LEFT_TEMPLE_TAP, MouseScrollAction(amount=-3)),
        (
            BindableGesture.RIGHT_TEMPLE_HOLD,
            ContinuousScrollAction(amount=2, interval_ms=100),
        ),
        (BindableGesture.LEFT_WINK, KeyboardKeyAction(key=KeyName.ENTER)),
        (
            BindableGesture.RIGHT_WINK,
            KeyboardShortcutAction(keys=(KeyName.CTRL, KeyName.SHIFT, KeyName.A)),
        ),
        (BindableGesture.LEFT_WINK, PauseTrackingAction()),
        (BindableGesture.RIGHT_WINK, ResumeTrackingAction()),
        (BindableGesture.LEFT_TEMPLE_TAP, ToggleTrackingAction()),
    ],
)
def test_action_codec_round_trips_every_supported_action(
    gesture: BindableGesture,
    action: Action,
) -> None:
    kind = action_kind_for(action)
    parameters = format_action_parameters(action)

    assert parse_action(gesture, kind, parameters) == action
    assert action_kind_label(kind)
    assert action_parameter_hint(kind)
    assert action_accepts_parameters(kind) is bool(parameters)


def test_non_hold_gestures_hide_hold_only_actions() -> None:
    choices = editable_action_kinds(BindableGesture.LEFT_WINK)

    assert EditableActionKind.MOUSE_DOWN not in choices
    assert EditableActionKind.CONTINUOUS_SCROLL not in choices
    assert editable_action_kinds(BindableGesture.LEFT_TEMPLE_HOLD) == tuple(EditableActionKind)


@pytest.mark.parametrize(
    ("gesture", "kind", "parameters", "message"),
    [
        (
            BindableGesture.LEFT_WINK,
            EditableActionKind.MOUSE_DOWN,
            "left",
            "only for temple hold",
        ),
        (
            BindableGesture.LEFT_WINK,
            EditableActionKind.MOUSE_CLICK,
            "side",
            "left, right, or middle",
        ),
        (
            BindableGesture.LEFT_WINK,
            EditableActionKind.MOUSE_SCROLL,
            "0",
            "non-zero whole number",
        ),
        (
            BindableGesture.LEFT_TEMPLE_HOLD,
            EditableActionKind.CONTINUOUS_SCROLL,
            "-2 100",
            "amount, milliseconds",
        ),
        (
            BindableGesture.LEFT_TEMPLE_HOLD,
            EditableActionKind.CONTINUOUS_SCROLL,
            "-2, 5",
            "interval 25 to 5000",
        ),
        (
            BindableGesture.LEFT_WINK,
            EditableActionKind.KEYBOARD_KEY,
            "NOT_A_KEY",
            "supported key name",
        ),
        (
            BindableGesture.LEFT_WINK,
            EditableActionKind.KEYBOARD_SHORTCUT,
            "CTRL + ALT",
            "one key",
        ),
        (
            BindableGesture.LEFT_WINK,
            EditableActionKind.DISABLED,
            "unexpected",
            "Remove parameters",
        ),
    ],
)
def test_action_codec_rejects_invalid_or_unsafe_editor_input(
    gesture: BindableGesture,
    kind: EditableActionKind,
    parameters: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_action(gesture, kind, parameters)


def test_action_codec_normalizes_whitespace_and_case() -> None:
    assert parse_action(
        BindableGesture.LEFT_WINK,
        EditableActionKind.KEYBOARD_SHORTCUT,
        " ctrl+Shift+a ",
    ) == KeyboardShortcutAction(keys=(KeyName.CTRL, KeyName.SHIFT, KeyName.A))
    assert parse_action(
        BindableGesture.RIGHT_WINK,
        EditableActionKind.MOUSE_CLICK,
        " RIGHT ",
    ) == MouseClickAction(button=MouseButton.RIGHT)


def test_action_codec_bounds_untrusted_parameter_text() -> None:
    with pytest.raises(ValueError, match="at most 200"):
        parse_action(
            BindableGesture.LEFT_WINK,
            EditableActionKind.MOUSE_SCROLL,
            "9" * 201,
        )
