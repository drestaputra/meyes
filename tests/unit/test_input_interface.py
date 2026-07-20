"""No-OS executor protocol and in-memory fake tests."""

from __future__ import annotations

import pytest

from meyes.domain.actions import KeyName, MouseButton
from meyes.input.fake import FakeInputExecutor, InputCall, InputReleaseError
from meyes.input.interface import InputExecutor


def test_fake_implements_platform_neutral_protocol() -> None:
    assert isinstance(FakeInputExecutor(), InputExecutor)


def test_fake_records_primitives_and_held_state() -> None:
    executor = FakeInputExecutor()

    executor.move_pointer(10, 20)
    executor.mouse_click(MouseButton.LEFT)
    executor.mouse_down(MouseButton.RIGHT)
    executor.mouse_scroll(-3)
    executor.key_down(KeyName.A)

    assert executor.held_buttons == {MouseButton.RIGHT}
    assert executor.held_keys == {KeyName.A}
    assert executor.calls[:3] == [
        InputCall("move_pointer", (10, 20)),
        InputCall("mouse_click", (MouseButton.LEFT,)),
        InputCall("mouse_down", (MouseButton.RIGHT,)),
    ]


def test_shortcut_releases_keys_in_reverse_order() -> None:
    executor = FakeInputExecutor()

    executor.keyboard_shortcut((KeyName.CTRL, KeyName.SHIFT, KeyName.TAB))

    assert executor.held_keys == set()
    assert executor.calls == [
        InputCall("keyboard_shortcut", (KeyName.CTRL, KeyName.SHIFT, KeyName.TAB)),
        InputCall("key_down", (KeyName.CTRL,)),
        InputCall("key_down", (KeyName.SHIFT,)),
        InputCall("key_down", (KeyName.TAB,)),
        InputCall("key_up", (KeyName.TAB,)),
        InputCall("key_up", (KeyName.SHIFT,)),
        InputCall("key_up", (KeyName.CTRL,)),
    ]


def test_release_all_is_state_idempotent_and_retryable() -> None:
    executor = FakeInputExecutor()
    executor.mouse_down(MouseButton.MIDDLE)
    executor.key_down(KeyName.CTRL)

    executor.release_all()
    first_calls = tuple(executor.calls)
    executor.release_all()

    assert executor.held_buttons == set()
    assert executor.held_keys == set()
    assert executor.release_all_calls == 2
    assert executor.calls.count(InputCall("mouse_up", (MouseButton.MIDDLE,))) == 1
    assert executor.calls.count(InputCall("key_up", (KeyName.CTRL,))) == 1
    assert tuple(executor.calls[: len(first_calls)]) == first_calls


def test_release_all_uses_reverse_acquisition_order() -> None:
    executor = FakeInputExecutor()
    executor.key_down(KeyName.CTRL)
    executor.mouse_down(MouseButton.LEFT)
    executor.key_down(KeyName.A)

    executor.release_all()

    assert executor.calls[-4:] == [
        InputCall("key_up", (KeyName.A,)),
        InputCall("mouse_up", (MouseButton.LEFT,)),
        InputCall("key_up", (KeyName.CTRL,)),
        InputCall("release_all"),
    ]


def test_drain_calls_bounds_diagnostics_without_changing_held_state() -> None:
    executor = FakeInputExecutor()
    executor.mouse_down(MouseButton.LEFT)
    executor.key_down(KeyName.CTRL)

    drained = executor.drain_calls()

    assert drained == (
        InputCall("mouse_down", (MouseButton.LEFT,)),
        InputCall("key_down", (KeyName.CTRL,)),
    )
    assert executor.calls == []
    assert executor.held_buttons == {MouseButton.LEFT}
    assert executor.held_keys == {KeyName.CTRL}

    executor.release_all()

    assert executor.held_buttons == set()
    assert executor.held_keys == set()


def test_release_all_attempts_every_input_then_retries_a_failure() -> None:
    class FailFirstARelease(FakeInputExecutor):
        failed = False

        def key_up(self, key: KeyName) -> None:
            if key is KeyName.A and not self.failed:
                self.failed = True
                raise OSError("injected A release failure")
            super().key_up(key)

    executor = FailFirstARelease()
    executor.key_down(KeyName.CTRL)
    executor.mouse_down(MouseButton.LEFT)
    executor.key_down(KeyName.A)

    with pytest.raises(InputReleaseError) as captured:
        executor.release_all()

    assert len(captured.value.errors) == 1
    assert executor.held_keys == {KeyName.A}
    assert executor.held_buttons == set()
    assert InputCall("key_up", (KeyName.CTRL,)) in executor.calls
    assert InputCall("mouse_up", (MouseButton.LEFT,)) in executor.calls

    executor.release_all()

    assert executor.held_keys == set()
    assert executor.release_all_calls == 2


def test_shortcut_releases_a_key_that_failed_after_partial_press() -> None:
    class FailAfterADown(FakeInputExecutor):
        def key_down(self, key: KeyName) -> None:
            super().key_down(key)
            if key is KeyName.A:
                raise OSError("injected A press failure")

    executor = FailAfterADown()

    with pytest.raises(OSError, match="press failure"):
        executor.keyboard_shortcut((KeyName.CTRL, KeyName.A))

    assert executor.held_keys == set()
    assert executor.calls[-2:] == [
        InputCall("key_up", (KeyName.A,)),
        InputCall("key_up", (KeyName.CTRL,)),
    ]
