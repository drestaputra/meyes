"""Validated logical gesture binding profiles."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_serializer,
    field_validator,
    model_validator,
)

from meyes.domain.actions import Action, ActionModel, ContinuousScrollAction, MouseDownAction
from meyes.util.profile_names import validate_profile_name

_ACTION_ADAPTER: TypeAdapter[Action] = TypeAdapter(Action)


class BindableGesture(StrEnum):
    """User-facing logical gestures; lifecycle end events are not bindings."""

    LEFT_WINK = "LEFT_WINK"
    RIGHT_WINK = "RIGHT_WINK"
    LEFT_TEMPLE_TAP = "LEFT_TEMPLE_TAP"
    RIGHT_TEMPLE_TAP = "RIGHT_TEMPLE_TAP"
    LEFT_TEMPLE_HOLD = "LEFT_TEMPLE_HOLD"
    RIGHT_TEMPLE_HOLD = "RIGHT_TEMPLE_HOLD"


class _FrozenBindings(Mapping[BindableGesture, Action]):
    """Read-only mapping that remains safe under Pydantic deep copies."""

    def __init__(self, values: Mapping[BindableGesture, Action]) -> None:
        self._values = MappingProxyType(dict(values))

    def __getitem__(self, key: BindableGesture) -> Action:
        return self._values[key]

    def __iter__(self) -> Iterator[BindableGesture]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __deepcopy__(self, memo: dict[int, object]) -> _FrozenBindings:
        del memo
        return self


HOLD_GESTURES = frozenset({BindableGesture.LEFT_TEMPLE_HOLD, BindableGesture.RIGHT_TEMPLE_HOLD})


class BindingProfile(BaseModel):
    """Complete, versioned binding snapshot for one named profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    profile_name: str = Field(min_length=1, max_length=80)
    bindings: Mapping[BindableGesture, Action]

    @field_validator("profile_name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> object:
        return validate_profile_name(value)

    @model_validator(mode="after")
    def validate_complete_safe_bindings(self) -> Self:
        expected = set(BindableGesture)
        actual = set(self.bindings)
        if actual != expected:
            missing = sorted(item.value for item in expected - actual)
            extra = sorted(str(item) for item in actual - expected)
            raise ValueError(
                f"bindings must contain exactly six gestures; missing={missing}, extra={extra}"
            )
        validated_bindings: dict[BindableGesture, Action] = {}
        for gesture, action in self.bindings.items():
            if not isinstance(action, ActionModel):
                raise ValueError("binding action must be a supported ActionModel")
            validated_action = _ACTION_ADAPTER.validate_python(
                action.model_dump(mode="python", warnings="none")
            )
            if (
                isinstance(validated_action, (ContinuousScrollAction, MouseDownAction))
                and gesture not in HOLD_GESTURES
            ):
                raise ValueError(f"{validated_action.type} requires a temple hold binding")
            validated_bindings[gesture] = validated_action
        object.__setattr__(self, "bindings", _FrozenBindings(validated_bindings))
        return self

    @field_serializer("bindings")
    def serialize_bindings(
        self,
        bindings: Mapping[BindableGesture, Action],
    ) -> dict[BindableGesture, Action]:
        return dict(bindings)
