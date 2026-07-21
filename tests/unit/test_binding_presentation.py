"""Stable human-readable labels for the complete action vocabulary."""

from __future__ import annotations

import pytest

from meyes.bindings.presentation import action_label
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
    ("action", "expected"),
    [
        (DisabledAction(), "Disabled"),
        (MouseClickAction(button=MouseButton.LEFT), "Mouse click · left"),
        (MouseDoubleClickAction(button=MouseButton.RIGHT), "Mouse double-click · right"),
        (MouseDownAction(button=MouseButton.MIDDLE), "Hold mouse button · middle"),
        (MouseUpAction(button=MouseButton.LEFT), "Release mouse button · left"),
        (MouseScrollAction(amount=-3), "Mouse scroll down · 3 steps"),
        (
            ContinuousScrollAction(amount=2, interval_ms=100),
            "Continuous scroll up · 2 every 100 ms",
        ),
        (KeyboardKeyAction(key=KeyName.ENTER), "Keyboard key · ENTER"),
        (
            KeyboardShortcutAction(keys=(KeyName.CTRL, KeyName.SHIFT, KeyName.A)),
            "Keyboard shortcut · CTRL + SHIFT + A",
        ),
        (PauseTrackingAction(), "Pause tracking"),
        (ResumeTrackingAction(), "Resume tracking"),
        (ToggleTrackingAction(), "Toggle tracking"),
    ],
)
def test_action_label_covers_every_supported_action(action: Action, expected: str) -> None:
    assert action_label(action) == expected
