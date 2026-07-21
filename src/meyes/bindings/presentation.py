"""Human-readable labels for validated gesture bindings."""

from __future__ import annotations

from meyes.bindings.models import BindableGesture
from meyes.domain.actions import (
    Action,
    ContinuousScrollAction,
    DisabledAction,
    KeyboardKeyAction,
    KeyboardShortcutAction,
    MouseClickAction,
    MouseDoubleClickAction,
    MouseDownAction,
    MouseScrollAction,
    MouseUpAction,
    PauseTrackingAction,
    ResumeTrackingAction,
    ToggleTrackingAction,
)

_GESTURE_LABELS = {
    BindableGesture.LEFT_WINK: "Left wink",
    BindableGesture.RIGHT_WINK: "Right wink",
    BindableGesture.LEFT_CHEEK_TOUCH: "Left cheek touch",
    BindableGesture.RIGHT_CHEEK_TOUCH: "Right cheek touch",
    BindableGesture.LEFT_TEMPLE_TAP: "Left temple tap",
    BindableGesture.RIGHT_TEMPLE_TAP: "Right temple tap",
    BindableGesture.LEFT_TEMPLE_HOLD: "Left temple hold",
    BindableGesture.RIGHT_TEMPLE_HOLD: "Right temple hold",
}


def gesture_label(gesture: BindableGesture) -> str:
    """Return the stable user-facing label for one logical gesture."""
    if not isinstance(gesture, BindableGesture):
        raise TypeError("Expected BindableGesture")
    return _GESTURE_LABELS[gesture]


def action_label(action: Action) -> str:
    """Describe a validated action without implying operating-system execution."""
    if isinstance(action, DisabledAction):
        return "Disabled"
    if isinstance(action, MouseClickAction):
        return f"Mouse click · {action.button.value}"
    if isinstance(action, MouseDoubleClickAction):
        return f"Mouse double-click · {action.button.value}"
    if isinstance(action, MouseDownAction):
        return f"Hold mouse button · {action.button.value}"
    if isinstance(action, MouseUpAction):
        return f"Release mouse button · {action.button.value}"
    if isinstance(action, MouseScrollAction):
        direction = "up" if action.amount > 0 else "down"
        return f"Mouse scroll {direction} · {abs(action.amount)} steps"
    if isinstance(action, ContinuousScrollAction):
        direction = "up" if action.amount > 0 else "down"
        return f"Continuous scroll {direction} · {abs(action.amount)} every {action.interval_ms} ms"
    if isinstance(action, KeyboardKeyAction):
        return f"Keyboard key · {action.key.value}"
    if isinstance(action, KeyboardShortcutAction):
        keys = " + ".join(key.value for key in action.keys)
        return f"Keyboard shortcut · {keys}"
    if isinstance(action, PauseTrackingAction):
        return "Pause tracking"
    if isinstance(action, ResumeTrackingAction):
        return "Resume tracking"
    if isinstance(action, ToggleTrackingAction):
        return "Toggle tracking"
    raise TypeError("Expected supported action")
