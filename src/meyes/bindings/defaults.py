"""Built-in and fail-closed binding profile factories."""

from __future__ import annotations

from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.domain.actions import (
    ContinuousScrollAction,
    DisabledAction,
    MouseButton,
    MouseClickAction,
    MouseScrollAction,
)
from meyes.util.profile_names import validate_profile_name

DEFAULT_PROFILE_NAME = "Default"


def default_profile() -> BindingProfile:
    """Return a fresh built-in profile matching the product specification."""
    return BindingProfile(
        profile_name=DEFAULT_PROFILE_NAME,
        bindings={
            BindableGesture.LEFT_WINK: MouseClickAction(button=MouseButton.LEFT),
            BindableGesture.RIGHT_WINK: MouseClickAction(button=MouseButton.RIGHT),
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
        },
    )


def disabled_profile(profile_name: str) -> BindingProfile:
    """Return a complete profile with every gesture disabled."""
    normalized = validate_profile_name(profile_name)
    return BindingProfile(
        profile_name=normalized,
        bindings={gesture: DisabledAction() for gesture in BindableGesture},
    )
