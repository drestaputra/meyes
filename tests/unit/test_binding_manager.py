"""Pure binding profile and semantic event resolution tests."""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import ValidationError

from meyes.bindings.defaults import default_profile, disabled_profile
from meyes.bindings.manager import BindingManager, BindingPhase
from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.domain.actions import (
    Action,
    ContinuousScrollAction,
    DisabledAction,
    KeyboardKeyAction,
    KeyName,
    MouseButton,
    MouseClickAction,
    MouseDownAction,
    MouseScrollAction,
)
from meyes.domain.events import GestureEvent, GestureEventType


def event(event_type: GestureEventType) -> GestureEvent:
    return GestureEvent(event_type, timestamp=1.0, source_sequence=7, duration_ms=120.0)


def test_default_profile_matches_specification_exactly() -> None:
    profile = default_profile()

    assert profile.profile_name == "Default"
    assert profile.bindings == {
        BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT),
        BindableGesture.RIGHT_WINK: MouseClickAction(button=MouseButton.RIGHT),
        BindableGesture.LEFT_CHEEK_TOUCH: DisabledAction(),
        BindableGesture.RIGHT_CHEEK_TOUCH: DisabledAction(),
        BindableGesture.LEFT_TEMPLE_TAP: MouseScrollAction(amount=-3),
        BindableGesture.RIGHT_TEMPLE_TAP: MouseScrollAction(amount=3),
        BindableGesture.LEFT_TEMPLE_HOLD: ContinuousScrollAction(
            amount=-2,
            interval_ms=100,
        ),
        BindableGesture.RIGHT_TEMPLE_HOLD: ContinuousScrollAction(
            amount=2,
            interval_ms=100,
        ),
    }


def test_default_temple_scroll_direction_is_right_up_and_left_down() -> None:
    bindings = default_profile().bindings
    left_tap = cast(MouseScrollAction, bindings[BindableGesture.LEFT_TEMPLE_TAP])
    right_tap = cast(MouseScrollAction, bindings[BindableGesture.RIGHT_TEMPLE_TAP])
    left_hold = cast(ContinuousScrollAction, bindings[BindableGesture.LEFT_TEMPLE_HOLD])
    right_hold = cast(ContinuousScrollAction, bindings[BindableGesture.RIGHT_TEMPLE_HOLD])

    assert left_tap.amount < 0
    assert left_hold.amount < 0
    assert right_tap.amount > 0
    assert right_hold.amount > 0


def test_disabled_profile_explicitly_disables_every_gesture() -> None:
    profile = disabled_profile("Recovery")

    assert set(profile.bindings) == set(BindableGesture)
    assert all(isinstance(action, DisabledAction) for action in profile.bindings.values())


def test_profile_deep_copy_preserves_read_only_bindings() -> None:
    copied = default_profile().model_copy(deep=True)

    assert copied == default_profile()
    with pytest.raises(TypeError):
        copied.bindings[BindableGesture.LEFT_WINK] = DisabledAction()  # type: ignore[index]


def test_profile_requires_all_eight_logical_gestures() -> None:
    bindings = dict(default_profile().bindings)
    bindings.pop(BindableGesture.LEFT_WINK)

    with pytest.raises(ValidationError, match="exactly eight"):
        BindingProfile(profile_name="Incomplete", bindings=bindings)


@pytest.mark.parametrize("include_schema", [False, True])
def test_legacy_profile_migrates_with_cheek_touches_disabled(include_schema: bool) -> None:
    legacy_bindings = dict(default_profile().bindings)
    legacy_bindings.pop(BindableGesture.LEFT_CHEEK_TOUCH)
    legacy_bindings.pop(BindableGesture.RIGHT_CHEEK_TOUCH)
    payload: dict[str, object] = {
        "profile_name": "Legacy",
        "bindings": legacy_bindings,
    }
    if include_schema:
        payload["schema_version"] = 1

    migrated = BindingProfile.model_validate(payload)

    assert migrated.schema_version == 2
    assert isinstance(migrated.bindings[BindableGesture.LEFT_CHEEK_TOUCH], DisabledAction)
    assert isinstance(migrated.bindings[BindableGesture.RIGHT_CHEEK_TOUCH], DisabledAction)


@pytest.mark.parametrize(
    "profile_name",
    ["../Escape", "folder/name", "bad:name", "CON", "LPT1.txt", ".", "name."],
)
def test_profile_names_are_windows_safe(profile_name: str) -> None:
    with pytest.raises(ValidationError, match="profile name"):
        BindingProfile(
            profile_name=profile_name,
            bindings=dict(default_profile().bindings),
        )


@pytest.mark.parametrize(
    "gesture",
    [
        BindableGesture.LEFT_WINK,
        BindableGesture.RIGHT_WINK,
        BindableGesture.LEFT_CHEEK_TOUCH,
        BindableGesture.RIGHT_CHEEK_TOUCH,
        BindableGesture.LEFT_TEMPLE_TAP,
        BindableGesture.RIGHT_TEMPLE_TAP,
    ],
)
@pytest.mark.parametrize(
    "action",
    [
        ContinuousScrollAction(amount=1, interval_ms=100),
        MouseDownAction(button=MouseButton.LEFT),
    ],
)
def test_actions_requiring_an_end_event_are_hold_only(
    gesture: BindableGesture,
    action: ContinuousScrollAction | MouseDownAction,
) -> None:
    bindings = dict(default_profile().bindings)
    bindings[gesture] = action

    with pytest.raises(ValidationError, match="requires a temple hold"):
        BindingProfile(profile_name="Unsafe", bindings=bindings)


@pytest.mark.parametrize(
    ("event_type", "gesture", "phase"),
    [
        (GestureEventType.LEFT_WINK, BindableGesture.LEFT_WINK, BindingPhase.TRIGGER),
        (GestureEventType.RIGHT_WINK, BindableGesture.RIGHT_WINK, BindingPhase.TRIGGER),
        (
            GestureEventType.LEFT_CHEEK_TOUCH,
            BindableGesture.LEFT_CHEEK_TOUCH,
            BindingPhase.TRIGGER,
        ),
        (
            GestureEventType.RIGHT_CHEEK_TOUCH,
            BindableGesture.RIGHT_CHEEK_TOUCH,
            BindingPhase.TRIGGER,
        ),
        (
            GestureEventType.LEFT_TEMPLE_TAP,
            BindableGesture.LEFT_TEMPLE_TAP,
            BindingPhase.TRIGGER,
        ),
        (
            GestureEventType.RIGHT_TEMPLE_TAP,
            BindableGesture.RIGHT_TEMPLE_TAP,
            BindingPhase.TRIGGER,
        ),
        (
            GestureEventType.LEFT_TEMPLE_HOLD_START,
            BindableGesture.LEFT_TEMPLE_HOLD,
            BindingPhase.START,
        ),
        (
            GestureEventType.RIGHT_TEMPLE_HOLD_START,
            BindableGesture.RIGHT_TEMPLE_HOLD,
            BindingPhase.START,
        ),
        (
            GestureEventType.LEFT_TEMPLE_HOLD_END,
            BindableGesture.LEFT_TEMPLE_HOLD,
            BindingPhase.END,
        ),
        (
            GestureEventType.RIGHT_TEMPLE_HOLD_END,
            BindableGesture.RIGHT_TEMPLE_HOLD,
            BindingPhase.END,
        ),
    ],
)
def test_manager_resolves_raw_events_to_logical_binding_phases(
    event_type: GestureEventType,
    gesture: BindableGesture,
    phase: BindingPhase,
) -> None:
    resolution = BindingManager().resolve(event(event_type))

    assert resolution.gesture is gesture
    assert resolution.phase is phase
    assert (resolution.action is None) is (phase is BindingPhase.END)


def test_hold_end_never_resolves_a_new_action_after_profile_change() -> None:
    manager = BindingManager()
    started = manager.resolve(event(GestureEventType.LEFT_TEMPLE_HOLD_START))
    manager.activate(disabled_profile("Disabled"))

    ended = manager.resolve(event(GestureEventType.LEFT_TEMPLE_HOLD_END))

    assert isinstance(started.action, ContinuousScrollAction)
    assert ended.phase is BindingPhase.END
    assert ended.action is None


def test_manager_copies_profiles_and_revalidates_each_update() -> None:
    manager = BindingManager(disabled_profile("Custom"))
    exposed = manager.active_profile

    with pytest.raises(TypeError):
        exposed.bindings[BindableGesture.LEFT_WINK] = MouseClickAction(  # type: ignore[index]
            button=MouseButton.LEFT
        )
    assert isinstance(manager.action_for(BindableGesture.LEFT_WINK), DisabledAction)
    updated = manager.set_binding(
        BindableGesture.LEFT_WINK,
        MouseClickAction(button=MouseButton.LEFT),
    )
    assert isinstance(updated.bindings[BindableGesture.LEFT_WINK], MouseClickAction)

    with pytest.raises(ValidationError, match="requires a temple hold"):
        manager.set_binding(
            BindableGesture.RIGHT_WINK,
            ContinuousScrollAction(amount=1, interval_ms=100),
        )


@pytest.mark.parametrize(
    ("gesture", "action"),
    [
        (
            BindableGesture.LEFT_TEMPLE_HOLD,
            ContinuousScrollAction(amount=1, interval_ms=100).model_copy(
                update={"amount": 0, "interval_ms": 1}
            ),
        ),
        (
            BindableGesture.LEFT_WINK,
            MouseClickAction(button=MouseButton.LEFT).model_copy(update={"button": "back"}),
        ),
        (
            BindableGesture.LEFT_TEMPLE_TAP,
            MouseScrollAction(amount=1).model_copy(update={"amount": 0}),
        ),
        (
            BindableGesture.RIGHT_WINK,
            KeyboardKeyAction(key=KeyName.A).model_copy(update={"key": "BAD"}),
        ),
    ],
)
def test_manager_revalidates_preconstructed_action_instances(
    gesture: BindableGesture,
    action: object,
) -> None:
    manager = BindingManager(disabled_profile("Safe"))

    with pytest.raises(ValidationError):
        manager.set_binding(gesture, cast(Action, action))


def test_manager_reset_returns_fresh_defaults() -> None:
    manager = BindingManager(disabled_profile("Custom"))

    reset = manager.reset_to_defaults()

    assert reset == default_profile()
