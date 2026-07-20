"""In-memory executor for tests and future no-input Safe Mode dispatch."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass

from meyes.domain.actions import KeyName, MouseButton
from meyes.input.interface import InputReleaseError as InputReleaseError


@dataclass(frozen=True, slots=True)
class InputCall:
    """One immutable primitive input call record."""

    operation: str
    arguments: tuple[object, ...] = ()


class FakeInputExecutor:
    """Record primitive calls and held state without touching the operating system."""

    def __init__(self) -> None:
        self.calls: list[InputCall] = []
        self.held_buttons: set[MouseButton] = set()
        self.held_keys: set[KeyName] = set()
        self._held_order: list[tuple[str, MouseButton | KeyName]] = []
        self.release_all_calls = 0

    def move_pointer(self, x: int, y: int) -> None:
        self.calls.append(InputCall("move_pointer", (x, y)))

    def mouse_click(self, button: MouseButton) -> None:
        self.calls.append(InputCall("mouse_click", (button,)))

    def mouse_down(self, button: MouseButton) -> None:
        if button not in self.held_buttons:
            self.held_buttons.add(button)
            self._held_order.append(("button", button))
        self.calls.append(InputCall("mouse_down", (button,)))

    def mouse_up(self, button: MouseButton) -> None:
        self.held_buttons.discard(button)
        self._remove_held("button", button)
        self.calls.append(InputCall("mouse_up", (button,)))

    def mouse_scroll(self, amount: int) -> None:
        self.calls.append(InputCall("mouse_scroll", (amount,)))

    def key_down(self, key: KeyName) -> None:
        if key not in self.held_keys:
            self.held_keys.add(key)
            self._held_order.append(("key", key))
        self.calls.append(InputCall("key_down", (key,)))

    def key_up(self, key: KeyName) -> None:
        self.held_keys.discard(key)
        self._remove_held("key", key)
        self.calls.append(InputCall("key_up", (key,)))

    def keyboard_shortcut(self, keys: tuple[KeyName, ...]) -> None:
        self.calls.append(InputCall("keyboard_shortcut", keys))
        held_order_start = len(self._held_order)
        try:
            for key in keys:
                self.key_down(key)
        finally:
            newly_held_keys = tuple(
                value
                for kind, value in self._held_order[held_order_start:]
                if kind == "key" and isinstance(value, KeyName)
            )
            errors = self._release_keys(reversed(newly_held_keys))
            if errors:
                raise InputReleaseError(tuple(errors))

    def release_all(self) -> None:
        self.release_all_calls += 1
        errors: list[Exception] = []
        for kind, value in reversed(tuple(self._held_order)):
            try:
                if kind == "key":
                    assert isinstance(value, KeyName)
                    self.key_up(value)
                else:
                    assert isinstance(value, MouseButton)
                    self.mouse_up(value)
            except Exception as error:
                errors.append(error)
        self.calls.append(InputCall("release_all"))
        if errors:
            raise InputReleaseError(tuple(errors))

    def drain_calls(self) -> tuple[InputCall, ...]:
        """Return and clear diagnostics records without changing held state."""
        calls = tuple(self.calls)
        self.calls.clear()
        return calls

    def _release_keys(self, keys: Iterable[KeyName]) -> list[Exception]:
        errors: list[Exception] = []
        for key in keys:
            try:
                self.key_up(key)
            except Exception as error:
                errors.append(error)
        return errors

    def _remove_held(self, kind: str, value: MouseButton | KeyName) -> None:
        with suppress(ValueError):
            self._held_order.remove((kind, value))
