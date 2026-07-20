"""Pure logical event-to-binding resolution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import TypeAdapter

from meyes.bindings.defaults import default_profile
from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.domain.actions import Action, ActionModel
from meyes.domain.events import GestureEvent, GestureEventType

_ACTION_ADAPTER: TypeAdapter[Action] = TypeAdapter(Action)


class BindingPhase(StrEnum):
    """How a semantic event relates to a logical binding."""

    TRIGGER = "trigger"
    START = "start"
    END = "end"


@dataclass(frozen=True, slots=True)
class BindingResolution:
    """One logical gesture resolution with no execution side effects."""

    gesture: BindableGesture
    phase: BindingPhase
    action: Action | None


_EVENT_BINDINGS: dict[GestureEventType, tuple[BindableGesture, BindingPhase]] = {
    GestureEventType.LEFT_WINK: (BindableGesture.LEFT_WINK, BindingPhase.TRIGGER),
    GestureEventType.RIGHT_WINK: (BindableGesture.RIGHT_WINK, BindingPhase.TRIGGER),
    GestureEventType.LEFT_TEMPLE_TAP: (
        BindableGesture.LEFT_TEMPLE_TAP,
        BindingPhase.TRIGGER,
    ),
    GestureEventType.RIGHT_TEMPLE_TAP: (
        BindableGesture.RIGHT_TEMPLE_TAP,
        BindingPhase.TRIGGER,
    ),
    GestureEventType.LEFT_TEMPLE_HOLD_START: (
        BindableGesture.LEFT_TEMPLE_HOLD,
        BindingPhase.START,
    ),
    GestureEventType.RIGHT_TEMPLE_HOLD_START: (
        BindableGesture.RIGHT_TEMPLE_HOLD,
        BindingPhase.START,
    ),
    GestureEventType.LEFT_TEMPLE_HOLD_END: (
        BindableGesture.LEFT_TEMPLE_HOLD,
        BindingPhase.END,
    ),
    GestureEventType.RIGHT_TEMPLE_HOLD_END: (
        BindableGesture.RIGHT_TEMPLE_HOLD,
        BindingPhase.END,
    ),
}


class BindingManager:
    """Maintain and resolve one validated active profile."""

    def __init__(self, profile: BindingProfile | None = None) -> None:
        self._profile = _validated_profile_copy(profile or default_profile())

    @property
    def active_profile(self) -> BindingProfile:
        """Return an isolated copy of the active profile."""
        return _validated_profile_copy(self._profile)

    def activate(self, profile: BindingProfile) -> None:
        """Replace the active profile with an isolated validated snapshot."""
        if not isinstance(profile, BindingProfile):
            raise TypeError("Expected BindingProfile")
        self._profile = _validated_profile_copy(profile)

    def reset_to_defaults(self) -> BindingProfile:
        """Restore and return a fresh copy of the built-in defaults."""
        self._profile = default_profile()
        return self.active_profile

    def set_binding(self, gesture: BindableGesture, action: Action) -> BindingProfile:
        """Validate and replace one binding by rebuilding the complete profile."""
        if not isinstance(gesture, BindableGesture):
            raise TypeError("Expected BindableGesture")
        if not isinstance(action, ActionModel):
            raise TypeError("Expected supported ActionModel")
        validated_action = _ACTION_ADAPTER.validate_python(
            action.model_dump(mode="python", warnings="none")
        )
        bindings = dict(self._profile.bindings)
        bindings[gesture] = validated_action
        self._profile = BindingProfile(
            schema_version=self._profile.schema_version,
            profile_name=self._profile.profile_name,
            bindings=bindings,
        )
        return self.active_profile

    def action_for(self, gesture: BindableGesture) -> Action:
        """Return an isolated configured action for one logical gesture."""
        if not isinstance(gesture, BindableGesture):
            raise TypeError("Expected BindableGesture")
        return self._profile.bindings[gesture].model_copy(deep=True)

    def resolve(self, event: GestureEvent) -> BindingResolution:
        """Resolve a semantic event without creating lifecycle end actions."""
        if not isinstance(event, GestureEvent):
            raise TypeError("Expected GestureEvent")
        if not isinstance(event.type, GestureEventType):
            raise TypeError("GestureEvent has an invalid event type")
        gesture, phase = _EVENT_BINDINGS[event.type]
        action = None if phase is BindingPhase.END else self.action_for(gesture)
        return BindingResolution(gesture, phase, action)


def _validated_profile_copy(profile: BindingProfile) -> BindingProfile:
    return BindingProfile.model_validate(profile.model_dump(mode="python", warnings="none"))
