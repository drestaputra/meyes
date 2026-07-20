"""Validated platform-neutral actions produced by the binding layer."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


class MouseButton(StrEnum):
    """Mouse buttons supported by the future Windows input backend."""

    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class KeyName(StrEnum):
    """Closed MVP key vocabulary shared by validation and future backends."""

    CTRL = "CTRL"
    ALT = "ALT"
    SHIFT = "SHIFT"
    WIN = "WIN"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"
    LETTER_I = "I"
    J = "J"
    K = "K"
    L = "L"
    M = "M"
    N = "N"
    LETTER_O = "O"
    P = "P"
    Q = "Q"
    R = "R"
    S = "S"
    T = "T"
    U = "U"
    V = "V"
    W = "W"
    X = "X"
    Y = "Y"
    Z = "Z"
    DIGIT_0 = "0"
    DIGIT_1 = "1"
    DIGIT_2 = "2"
    DIGIT_3 = "3"
    DIGIT_4 = "4"
    DIGIT_5 = "5"
    DIGIT_6 = "6"
    DIGIT_7 = "7"
    DIGIT_8 = "8"
    DIGIT_9 = "9"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"
    F8 = "F8"
    F9 = "F9"
    F10 = "F10"
    F11 = "F11"
    F12 = "F12"
    F13 = "F13"
    F14 = "F14"
    F15 = "F15"
    F16 = "F16"
    F17 = "F17"
    F18 = "F18"
    F19 = "F19"
    F20 = "F20"
    F21 = "F21"
    F22 = "F22"
    F23 = "F23"
    F24 = "F24"
    TAB = "TAB"
    ENTER = "ENTER"
    ESC = "ESC"
    SPACE = "SPACE"
    BACKSPACE = "BACKSPACE"
    DELETE = "DELETE"
    INSERT = "INSERT"
    HOME = "HOME"
    END = "END"
    PAGE_UP = "PAGE_UP"
    PAGE_DOWN = "PAGE_DOWN"
    ARROW_LEFT = "ARROW_LEFT"
    ARROW_RIGHT = "ARROW_RIGHT"
    ARROW_UP = "ARROW_UP"
    ARROW_DOWN = "ARROW_DOWN"


MODIFIER_KEYS = frozenset({KeyName.CTRL, KeyName.ALT, KeyName.SHIFT, KeyName.WIN})


class ActionModel(BaseModel):
    """Immutable action base that rejects unsupported payload fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DisabledAction(ActionModel):
    """Explicitly disable one logical gesture."""

    type: Literal["disabled"] = "disabled"


class MouseClickAction(ActionModel):
    """Click one supported mouse button once."""

    type: Literal["mouse_click"] = "mouse_click"
    button: MouseButton


class MouseDoubleClickAction(ActionModel):
    """Click one supported mouse button twice."""

    type: Literal["mouse_double_click"] = "mouse_double_click"
    button: MouseButton


class MouseDownAction(ActionModel):
    """Press a mouse button until the owning hold ends or safety release runs."""

    type: Literal["mouse_down"] = "mouse_down"
    button: MouseButton


class MouseUpAction(ActionModel):
    """Release one supported mouse button."""

    type: Literal["mouse_up"] = "mouse_up"
    button: MouseButton


class _BoundedScrollAction(ActionModel):
    amount: StrictInt = Field(ge=-20, le=20)

    @field_validator("amount")
    @classmethod
    def reject_zero_amount(cls, value: int) -> int:
        if value == 0:
            raise ValueError("scroll amount must be nonzero")
        return value


class MouseScrollAction(_BoundedScrollAction):
    """Apply one finite scroll step."""

    type: Literal["mouse_scroll"] = "mouse_scroll"


class ContinuousScrollAction(_BoundedScrollAction):
    """Describe poll-driven scroll repeated while a logical hold owns it."""

    type: Literal["mouse_scroll_continuous"] = "mouse_scroll_continuous"
    interval_ms: StrictInt = Field(ge=25, le=5000)


class KeyboardKeyAction(ActionModel):
    """Tap one supported keyboard key."""

    type: Literal["keyboard_key"] = "keyboard_key"
    key: KeyName

    @field_validator("key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> object:
        return _normalize_key(value)


class KeyboardShortcutAction(ActionModel):
    """Tap a conventional modifier chord with one non-modifier key."""

    type: Literal["keyboard_shortcut"] = "keyboard_shortcut"
    keys: tuple[KeyName, ...] = Field(min_length=1, max_length=5)

    @field_validator("keys", mode="before")
    @classmethod
    def normalize_keys(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
            raise ValueError("shortcut keys must be a list or tuple")
        return tuple(_normalize_key(item) for item in value)

    @model_validator(mode="after")
    def validate_chord(self) -> Self:
        if len(set(self.keys)) != len(self.keys):
            raise ValueError("shortcut keys must not contain duplicates")
        non_modifiers = [key for key in self.keys if key not in MODIFIER_KEYS]
        if len(non_modifiers) != 1:
            raise ValueError("shortcut must contain exactly one non-modifier key")
        if self.keys[-1] is not non_modifiers[0]:
            raise ValueError("shortcut modifiers must precede the non-modifier key")
        return self


class PauseTrackingAction(ActionModel):
    """Request the application safety lifecycle to pause tracking."""

    type: Literal["pause_tracking"] = "pause_tracking"


class ResumeTrackingAction(ActionModel):
    """Request tracking resume through the application lifecycle."""

    type: Literal["resume_tracking"] = "resume_tracking"


class ToggleTrackingAction(ActionModel):
    """Request a tracking state toggle through the application lifecycle."""

    type: Literal["toggle_tracking"] = "toggle_tracking"


Action: TypeAlias = Annotated[
    DisabledAction
    | MouseClickAction
    | MouseDoubleClickAction
    | MouseDownAction
    | MouseUpAction
    | MouseScrollAction
    | ContinuousScrollAction
    | KeyboardKeyAction
    | KeyboardShortcutAction
    | PauseTrackingAction
    | ResumeTrackingAction
    | ToggleTrackingAction,
    Field(discriminator="type"),
]


def _normalize_key(value: object) -> object:
    if not isinstance(value, str):
        raise ValueError("key name must be a string")
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("key name must not be empty")
    return normalized
