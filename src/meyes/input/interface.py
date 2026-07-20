"""Protocol implemented by test doubles and future platform input backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from meyes.domain.actions import KeyName, MouseButton


@runtime_checkable
class InputExecutor(Protocol):
    """Primitive input interface kept separate from gesture and binding code."""

    def move_pointer(self, x: int, y: int) -> None: ...

    def mouse_click(self, button: MouseButton) -> None: ...

    def mouse_down(self, button: MouseButton) -> None: ...

    def mouse_up(self, button: MouseButton) -> None: ...

    def mouse_scroll(self, amount: int) -> None: ...

    def key_down(self, key: KeyName) -> None: ...

    def key_up(self, key: KeyName) -> None: ...

    def keyboard_shortcut(self, keys: tuple[KeyName, ...]) -> None: ...

    def release_all(self) -> None: ...
