"""Windows SendInput executor tests with a non-native recording boundary."""

from __future__ import annotations

import ctypes
from collections import deque
from dataclasses import dataclass, field

import pytest

from meyes.cursor.screen_mapping import PhysicalScreenGeometry
from meyes.domain.actions import KeyName, MouseButton
from meyes.input.interface import InputCleanupError, InputExecutor, InputReleaseError
from meyes.input.windows_sendinput import (
    KEYEVENTF_EXTENDEDKEY,
    KEYEVENTF_KEYUP,
    MOUSEEVENTF_ABSOLUTE,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_MIDDLEDOWN,
    MOUSEEVENTF_MIDDLEUP,
    MOUSEEVENTF_MOVE,
    MOUSEEVENTF_RIGHTDOWN,
    MOUSEEVENTF_RIGHTUP,
    MOUSEEVENTF_WHEEL,
    WHEEL_DELTA,
    CtypesSendInputApi,
    SendInputApi,
    SendInputError,
    SendInputPacket,
    SendInputPacketKind,
    WindowsSendInputExecutor,
    native_input_size,
)


@dataclass(slots=True)
class RecordingSendInputApi:
    """Return scripted counts or errors without touching User32."""

    responses: deque[int | Exception] = field(default_factory=deque)
    error_code: int = 0
    calls: list[tuple[SendInputPacket, ...]] = field(default_factory=list)

    def send(self, packets: tuple[SendInputPacket, ...]) -> int:
        self.calls.append(packets)
        if not self.responses:
            return len(packets)
        response = self.responses.popleft()
        if isinstance(response, Exception):
            raise response
        return response

    def last_error(self) -> int:
        return self.error_code


@dataclass(slots=True)
class RecordingGeometryProvider:
    geometry: PhysicalScreenGeometry = field(
        default_factory=lambda: PhysicalScreenGeometry(100, 200, 1921, 1081)
    )
    reads: int = 0

    def read(self) -> PhysicalScreenGeometry:
        self.reads += 1
        return self.geometry


def test_executor_and_native_adapter_implement_their_protocols() -> None:
    api = RecordingSendInputApi()
    executor = WindowsSendInputExecutor(api)

    assert isinstance(api, SendInputApi)
    assert isinstance(executor, InputExecutor)
    assert isinstance(CtypesSendInputApi(), SendInputApi)
    expected_size = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert native_input_size() == expected_size
    assert api.calls == []


@pytest.mark.parametrize(
    ("button", "down_flag", "up_flag"),
    [
        (MouseButton.LEFT, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        (MouseButton.RIGHT, MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        (MouseButton.MIDDLE, MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    ],
)
def test_mouse_click_maps_complete_native_sequence(
    button: MouseButton,
    down_flag: int,
    up_flag: int,
) -> None:
    api = RecordingSendInputApi()
    executor = WindowsSendInputExecutor(api)

    executor.mouse_click(button)

    assert api.calls == [
        (
            SendInputPacket(SendInputPacketKind.MOUSE, flags=down_flag),
            SendInputPacket(SendInputPacketKind.MOUSE, flags=up_flag),
        )
    ]
    assert executor.held_buttons == frozenset()


def test_pointer_maps_primary_screen_pixels_to_absolute_sendinput_coordinates() -> None:
    api = RecordingSendInputApi()
    geometry = RecordingGeometryProvider()
    executor = WindowsSendInputExecutor(api, pointer_geometry_provider=geometry)

    executor.move_pointer(100, 200)
    executor.move_pointer(1060, 740)
    executor.move_pointer(2020, 1280)

    flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
    assert api.calls == [
        (SendInputPacket(SendInputPacketKind.MOUSE, flags=flags, dx=0, dy=0),),
        (SendInputPacket(SendInputPacketKind.MOUSE, flags=flags, dx=32768, dy=32768),),
        (SendInputPacket(SendInputPacketKind.MOUSE, flags=flags, dx=65535, dy=65535),),
    ]
    assert geometry.reads == 1


def test_pointer_rejects_pixels_outside_calibrated_primary_screen() -> None:
    api = RecordingSendInputApi()
    geometry = RecordingGeometryProvider()
    executor = WindowsSendInputExecutor(api, pointer_geometry_provider=geometry)

    with pytest.raises(ValueError, match="x must be inside"):
        executor.move_pointer(99, 500)
    with pytest.raises(ValueError, match="y must be inside"):
        executor.move_pointer(500, 1281)

    assert api.calls == []


@pytest.mark.parametrize("amount", [-20, -3, 1, 20])
def test_mouse_scroll_maps_logical_steps_to_wheel_delta(amount: int) -> None:
    api = RecordingSendInputApi()
    executor = WindowsSendInputExecutor(api)

    executor.mouse_scroll(amount)

    assert api.calls == [
        (
            SendInputPacket(
                SendInputPacketKind.MOUSE,
                flags=MOUSEEVENTF_WHEEL,
                mouse_data=amount * WHEEL_DELTA,
            ),
        )
    ]


@pytest.mark.parametrize(
    ("key", "virtual_key", "extended"),
    [
        (KeyName.CTRL, 0x11, False),
        (KeyName.A, ord("A"), False),
        (KeyName.DIGIT_7, ord("7"), False),
        (KeyName.F24, 0x87, False),
        (KeyName.DELETE, 0x2E, True),
        (KeyName.ARROW_DOWN, 0x28, True),
    ],
)
def test_keyboard_packets_use_closed_virtual_key_mapping(
    key: KeyName,
    virtual_key: int,
    extended: bool,
) -> None:
    api = RecordingSendInputApi()
    executor = WindowsSendInputExecutor(api)

    executor.key_down(key)
    executor.key_up(key)

    base_flags = KEYEVENTF_EXTENDEDKEY if extended else 0
    assert api.calls == [
        (
            SendInputPacket(
                SendInputPacketKind.KEYBOARD,
                flags=base_flags,
                virtual_key=virtual_key,
            ),
        ),
        (
            SendInputPacket(
                SendInputPacketKind.KEYBOARD,
                flags=base_flags | KEYEVENTF_KEYUP,
                virtual_key=virtual_key,
            ),
        ),
    ]
    assert executor.held_keys == frozenset()


def test_every_valid_key_has_a_native_mapping() -> None:
    api = RecordingSendInputApi()
    executor = WindowsSendInputExecutor(api)

    for key in KeyName:
        executor.key_down(key)
        executor.key_up(key)

    assert len(api.calls) == len(KeyName) * 2
    assert executor.held_keys == frozenset()


def test_shortcut_presses_in_order_and_releases_new_keys_in_reverse() -> None:
    api = RecordingSendInputApi()
    executor = WindowsSendInputExecutor(api)

    executor.keyboard_shortcut((KeyName.CTRL, KeyName.SHIFT, KeyName.A))

    packets = api.calls[0]
    assert [(packet.virtual_key, bool(packet.flags & KEYEVENTF_KEYUP)) for packet in packets] == [
        (0x11, False),
        (0x10, False),
        (ord("A"), False),
        (ord("A"), True),
        (0x10, True),
        (0x11, True),
    ]
    assert executor.held_keys == frozenset()


def test_release_all_uses_reverse_owned_acquisition_order() -> None:
    api = RecordingSendInputApi()
    executor = WindowsSendInputExecutor(api)
    executor.key_down(KeyName.CTRL)
    executor.mouse_down(MouseButton.LEFT)
    executor.key_down(KeyName.A)

    executor.release_all()

    release_calls = api.calls[-3:]
    assert release_calls[0][0].virtual_key == ord("A")
    assert release_calls[0][0].flags & KEYEVENTF_KEYUP
    assert release_calls[1][0].flags == MOUSEEVENTF_LEFTUP
    assert release_calls[2][0].virtual_key == 0x11
    assert release_calls[2][0].flags & KEYEVENTF_KEYUP
    assert executor.held_keys == frozenset()
    assert executor.held_buttons == frozenset()


def test_partial_click_is_released_then_reports_bounded_failure() -> None:
    api = RecordingSendInputApi(responses=deque([1, 1]), error_code=5)
    executor = WindowsSendInputExecutor(api)

    with pytest.raises(SendInputError) as captured:
        executor.mouse_click(MouseButton.LEFT)

    assert captured.value.requested == 2
    assert captured.value.sent == 1
    assert captured.value.error_code == 5
    assert api.calls[-1] == (SendInputPacket(SendInputPacketKind.MOUSE, flags=MOUSEEVENTF_LEFTUP),)
    assert executor.held_buttons == frozenset()


def test_partial_shortcut_releases_every_inserted_down_event() -> None:
    api = RecordingSendInputApi(responses=deque([2]))
    executor = WindowsSendInputExecutor(api)

    with pytest.raises(SendInputError, match="did not report a specific cause"):
        executor.keyboard_shortcut((KeyName.CTRL, KeyName.A))

    assert [call[0].virtual_key for call in api.calls[1:]] == [ord("A"), 0x11]
    assert all(call[0].flags & KEYEVENTF_KEYUP for call in api.calls[1:])
    assert executor.held_keys == frozenset()


def test_release_failure_is_aggregated_and_retryable() -> None:
    api = RecordingSendInputApi(error_code=5)
    executor = WindowsSendInputExecutor(api)
    executor.mouse_down(MouseButton.RIGHT)
    api.responses.append(0)

    with pytest.raises(InputReleaseError) as captured:
        executor.release_all()

    assert len(captured.value.errors) == 1
    assert executor.held_buttons == frozenset({MouseButton.RIGHT})
    executor.release_all()
    assert executor.held_buttons == frozenset()


def test_partial_transient_send_reports_primary_and_cleanup_failures() -> None:
    api = RecordingSendInputApi(responses=deque([1, 0]), error_code=5)
    executor = WindowsSendInputExecutor(api)

    with pytest.raises(InputCleanupError) as captured:
        executor.mouse_click(MouseButton.LEFT)

    assert isinstance(captured.value.primary_error, SendInputError)
    assert len(captured.value.release_errors) == 1
    assert executor.held_buttons == frozenset({MouseButton.LEFT})
    executor.release_all()
    assert executor.held_buttons == frozenset()


def test_unknown_native_exception_marks_press_as_possibly_held_for_cleanup() -> None:
    api = RecordingSendInputApi(responses=deque([OSError("injected native exception")]))
    executor = WindowsSendInputExecutor(api)

    with pytest.raises(OSError, match="injected"):
        executor.key_down(KeyName.A)

    assert executor.held_keys == frozenset({KeyName.A})
    executor.release_all()
    assert executor.held_keys == frozenset()


def test_invalid_primitives_fail_before_native_call() -> None:
    api = RecordingSendInputApi()
    executor = WindowsSendInputExecutor(api)

    with pytest.raises(TypeError, match="MouseButton"):
        executor.mouse_click("left")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="KeyName"):
        executor.key_down("A")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="nonzero"):
        executor.mouse_scroll(0)
    with pytest.raises(ValueError, match="1-5"):
        executor.keyboard_shortcut(())
    with pytest.raises(TypeError, match="x must be an integer"):
        executor.move_pointer(True, 20)

    assert api.calls == []
