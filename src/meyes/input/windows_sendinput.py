"""Opt-in Windows SendInput executor with owned-state fail-safe release."""

from __future__ import annotations

import ctypes
import os
import threading
from contextlib import suppress
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from meyes.domain.actions import KeyName, MouseButton
from meyes.input.interface import InputCleanupError, InputReleaseError

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120


class SendInputPacketKind(StrEnum):
    """Native packet category exposed for deterministic boundary tests."""

    MOUSE = "mouse"
    KEYBOARD = "keyboard"


@dataclass(frozen=True, slots=True)
class SendInputPacket:
    """Platform-width-independent description of one native INPUT event."""

    kind: SendInputPacketKind
    flags: int
    mouse_data: int = 0
    virtual_key: int = 0
    scan_code: int = 0


class SendInputError(OSError):
    """Disclose a bounded native send failure without claiming its cause."""

    def __init__(self, requested: int, sent: int, error_code: int) -> None:
        message = f"SendInput inserted {sent} of {requested} event(s)"
        if error_code:
            message = f"{message}; Windows error {error_code}"
        else:
            message = f"{message}; Windows did not report a specific cause"
        super().__init__(error_code, message)
        self.requested = requested
        self.sent = sent
        self.error_code = error_code


@runtime_checkable
class SendInputApi(Protocol):
    """Narrow Win32 boundary injected by unit tests."""

    def send(self, packets: tuple[SendInputPacket, ...]) -> int: ...

    def last_error(self) -> int: ...


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    )


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    )


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class _INPUTUNION(ctypes.Union):
    _fields_ = (
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    )


class _INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = (("type", wintypes.DWORD), ("data", _INPUTUNION))


class CtypesSendInputApi:
    """ctypes adapter for User32.SendInput; constructing it never sends input."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows SendInput is available only on Windows")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        send_input: Any = user32.SendInput
        send_input.argtypes = (
            wintypes.UINT,
            ctypes.POINTER(_INPUT),
            ctypes.c_int,
        )
        send_input.restype = wintypes.UINT
        self._send_input = send_input

    def send(self, packets: tuple[SendInputPacket, ...]) -> int:
        if not packets:
            return 0
        array_type = _INPUT * len(packets)
        native_packets = array_type(*(_native_input(packet) for packet in packets))
        return int(self._send_input(len(packets), native_packets, ctypes.sizeof(_INPUT)))

    def last_error(self) -> int:
        return int(ctypes.get_last_error())


@dataclass(frozen=True, slots=True)
class _HeldTransition:
    kind: str
    value: MouseButton | KeyName
    pressed: bool


class WindowsSendInputExecutor:
    """Send real mouse and keyboard primitives only when explicitly constructed."""

    def __init__(self, api: SendInputApi | None = None) -> None:
        native_api = api or CtypesSendInputApi()
        if not isinstance(native_api, SendInputApi):
            raise TypeError("Expected SendInputApi")
        self._api = native_api
        self._held_buttons: set[MouseButton] = set()
        self._held_keys: set[KeyName] = set()
        self._held_order: list[tuple[str, MouseButton | KeyName]] = []
        self._lock = threading.RLock()

    @property
    def held_buttons(self) -> frozenset[MouseButton]:
        with self._lock:
            return frozenset(self._held_buttons)

    @property
    def held_keys(self) -> frozenset[KeyName]:
        with self._lock:
            return frozenset(self._held_keys)

    def move_pointer(self, x: int, y: int) -> None:
        if isinstance(x, bool) or not isinstance(x, int):
            raise TypeError("x must be an integer")
        if isinstance(y, bool) or not isinstance(y, int):
            raise TypeError("y must be an integer")
        raise NotImplementedError("Pointer movement requires calibrated screen mapping")

    def mouse_click(self, button: MouseButton) -> None:
        selected = _validate_button(button)
        with self._lock:
            if selected in self._held_buttons:
                raise RuntimeError("Cannot click a mouse button already held by MEYES")
            down, up = _mouse_button_packets(selected)
            self._run_transient_sequence(
                (down, up),
                (
                    _HeldTransition("button", selected, True),
                    _HeldTransition("button", selected, False),
                ),
            )

    def mouse_down(self, button: MouseButton) -> None:
        selected = _validate_button(button)
        with self._lock:
            down, _up = _mouse_button_packets(selected)
            self._send_sequence(
                (down,),
                (_HeldTransition("button", selected, True),),
            )

    def mouse_up(self, button: MouseButton) -> None:
        selected = _validate_button(button)
        with self._lock:
            _down, up = _mouse_button_packets(selected)
            self._send_sequence(
                (up,),
                (_HeldTransition("button", selected, False),),
            )

    def mouse_scroll(self, amount: int) -> None:
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise TypeError("scroll amount must be an integer")
        if amount == 0 or not -20 <= amount <= 20:
            raise ValueError("scroll amount must be between -20 and 20 and nonzero")
        packet = SendInputPacket(
            SendInputPacketKind.MOUSE,
            flags=MOUSEEVENTF_WHEEL,
            mouse_data=amount * WHEEL_DELTA,
        )
        with self._lock:
            self._send_sequence((packet,), (None,))

    def key_down(self, key: KeyName) -> None:
        selected = _validate_key(key)
        with self._lock:
            self._send_sequence(
                (_keyboard_packet(selected, released=False),),
                (_HeldTransition("key", selected, True),),
            )

    def key_up(self, key: KeyName) -> None:
        selected = _validate_key(key)
        with self._lock:
            self._send_sequence(
                (_keyboard_packet(selected, released=True),),
                (_HeldTransition("key", selected, False),),
            )

    def keyboard_shortcut(self, keys: tuple[KeyName, ...]) -> None:
        if not isinstance(keys, tuple) or not keys or len(keys) > 5:
            raise ValueError("shortcut must contain 1-5 keys")
        selected = tuple(_validate_key(key) for key in keys)
        if len(set(selected)) != len(selected):
            raise ValueError("shortcut keys must not contain duplicates")
        with self._lock:
            newly_held = tuple(key for key in selected if key not in self._held_keys)
            packets = tuple(_keyboard_packet(key, released=False) for key in selected) + tuple(
                _keyboard_packet(key, released=True) for key in reversed(newly_held)
            )
            transitions = tuple(_HeldTransition("key", key, True) for key in selected) + tuple(
                _HeldTransition("key", key, False) for key in reversed(newly_held)
            )
            self._run_transient_sequence(packets, transitions)

    def release_all(self) -> None:
        with self._lock:
            errors = self._release_all_errors()
            if errors:
                raise InputReleaseError(tuple(errors))

    def _run_transient_sequence(
        self,
        packets: tuple[SendInputPacket, ...],
        transitions: tuple[_HeldTransition, ...],
    ) -> None:
        try:
            self._send_sequence(packets, transitions)
        except Exception as error:
            release_errors = self._release_all_errors()
            if release_errors:
                raise InputCleanupError(error, tuple(release_errors)) from error
            raise

    def _send_sequence(
        self,
        packets: tuple[SendInputPacket, ...],
        transitions: tuple[_HeldTransition | None, ...],
    ) -> None:
        if not packets or len(packets) != len(transitions):
            raise ValueError("native packets and transitions must be nonempty and aligned")
        try:
            sent = self._api.send(packets)
        except Exception:
            for transition in transitions:
                if transition is not None and transition.pressed:
                    self._apply_transition(transition)
            raise
        if isinstance(sent, bool) or not isinstance(sent, int) or not 0 <= sent <= len(packets):
            for transition in transitions:
                if transition is not None and transition.pressed:
                    self._apply_transition(transition)
            raise RuntimeError("SendInput returned an invalid event count")
        for transition in transitions[:sent]:
            if transition is not None:
                self._apply_transition(transition)
        if sent != len(packets):
            raise SendInputError(len(packets), sent, self._api.last_error())

    def _release_all_errors(self) -> list[Exception]:
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
        return errors

    def _apply_transition(self, transition: _HeldTransition) -> None:
        record = (transition.kind, transition.value)
        if transition.kind == "key":
            assert isinstance(transition.value, KeyName)
            if transition.pressed:
                if transition.value not in self._held_keys:
                    self._held_keys.add(transition.value)
                    self._held_order.append(record)
                return
            self._held_keys.discard(transition.value)
        else:
            assert isinstance(transition.value, MouseButton)
            if transition.pressed:
                if transition.value not in self._held_buttons:
                    self._held_buttons.add(transition.value)
                    self._held_order.append(record)
                return
            self._held_buttons.discard(transition.value)
        with suppress(ValueError):
            self._held_order.remove(record)


def native_input_size() -> int:
    """Expose the runtime INPUT structure size for ABI smoke tests."""
    return ctypes.sizeof(_INPUT)


def _native_input(packet: SendInputPacket) -> _INPUT:
    native = _INPUT()
    if packet.kind is SendInputPacketKind.MOUSE:
        native.type = INPUT_MOUSE
        native.mi = _MOUSEINPUT(
            0,
            0,
            packet.mouse_data & 0xFFFFFFFF,
            packet.flags,
            0,
            0,
        )
    elif packet.kind is SendInputPacketKind.KEYBOARD:
        native.type = INPUT_KEYBOARD
        native.ki = _KEYBDINPUT(
            packet.virtual_key,
            packet.scan_code,
            packet.flags,
            0,
            0,
        )
    else:
        raise ValueError("Unsupported SendInput packet kind")
    return native


def _mouse_button_packets(button: MouseButton) -> tuple[SendInputPacket, SendInputPacket]:
    flags = {
        MouseButton.LEFT: (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
        MouseButton.RIGHT: (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
        MouseButton.MIDDLE: (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    }
    down, up = flags[button]
    return (
        SendInputPacket(SendInputPacketKind.MOUSE, flags=down),
        SendInputPacket(SendInputPacketKind.MOUSE, flags=up),
    )


def _keyboard_packet(key: KeyName, *, released: bool) -> SendInputPacket:
    flags = KEYEVENTF_EXTENDEDKEY if key in _EXTENDED_KEYS else 0
    if released:
        flags |= KEYEVENTF_KEYUP
    return SendInputPacket(
        SendInputPacketKind.KEYBOARD,
        flags=flags,
        virtual_key=_VIRTUAL_KEYS[key],
    )


def _validate_button(button: MouseButton) -> MouseButton:
    if not isinstance(button, MouseButton):
        raise TypeError("Expected MouseButton")
    return button


def _validate_key(key: KeyName) -> KeyName:
    if not isinstance(key, KeyName):
        raise TypeError("Expected KeyName")
    return key


_VIRTUAL_KEYS: dict[KeyName, int] = {
    KeyName.CTRL: 0x11,
    KeyName.ALT: 0x12,
    KeyName.SHIFT: 0x10,
    KeyName.WIN: 0x5B,
    **{KeyName(chr(code)): code for code in range(ord("A"), ord("Z") + 1)},
    **{KeyName(str(number)): ord(str(number)) for number in range(10)},
    **{KeyName(f"F{number}"): 0x6F + number for number in range(1, 25)},
    KeyName.TAB: 0x09,
    KeyName.ENTER: 0x0D,
    KeyName.ESC: 0x1B,
    KeyName.SPACE: 0x20,
    KeyName.BACKSPACE: 0x08,
    KeyName.DELETE: 0x2E,
    KeyName.INSERT: 0x2D,
    KeyName.HOME: 0x24,
    KeyName.END: 0x23,
    KeyName.PAGE_UP: 0x21,
    KeyName.PAGE_DOWN: 0x22,
    KeyName.ARROW_LEFT: 0x25,
    KeyName.ARROW_UP: 0x26,
    KeyName.ARROW_RIGHT: 0x27,
    KeyName.ARROW_DOWN: 0x28,
}

_EXTENDED_KEYS = frozenset(
    {
        KeyName.DELETE,
        KeyName.INSERT,
        KeyName.HOME,
        KeyName.END,
        KeyName.PAGE_UP,
        KeyName.PAGE_DOWN,
        KeyName.ARROW_LEFT,
        KeyName.ARROW_UP,
        KeyName.ARROW_RIGHT,
        KeyName.ARROW_DOWN,
    }
)
