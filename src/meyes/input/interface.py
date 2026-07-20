"""Protocol implemented by test doubles and future platform input backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from meyes.domain.actions import KeyName, MouseButton


class InputReleaseError(RuntimeError):
    """Report one or more release failures after every held input was attempted."""

    def __init__(self, errors: tuple[Exception, ...]) -> None:
        super().__init__(f"Failed to release {len(errors)} held input(s)")
        self.errors = errors


class InputCleanupError(RuntimeError):
    """Report a primary input failure followed by one or more cleanup failures."""

    def __init__(self, primary_error: Exception, release_errors: tuple[Exception, ...]) -> None:
        super().__init__(
            f"Input failed and {len(release_errors)} fail-safe release attempt(s) also failed"
        )
        self.primary_error = primary_error
        self.release_errors = release_errors


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
