"""Windows emergency hotkey registration and physical-input preflight."""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from PySide6.QtCore import (
    QAbstractNativeEventFilter,
    QByteArray,
    QCoreApplication,
    QObject,
    Signal,
)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
EMERGENCY_HOTKEY_ID = 0x4D45
EMERGENCY_HOTKEY_MODIFIERS = MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT
EMERGENCY_HOTKEY_VIRTUAL_KEY = 0x7A  # F11; F12 is reserved by Windows debuggers.
EMERGENCY_HOTKEY_LABEL = "Ctrl+Alt+Shift+F11"


class WindowsHotkeyError(OSError):
    """Sanitized emergency hotkey registration or cleanup failure."""

    def __init__(self, operation: str, error_code: int) -> None:
        message = f"Emergency hotkey {operation} failed"
        if error_code:
            message = f"{message}; Windows error {error_code}"
        else:
            message = f"{message}; Windows did not report a specific cause"
        super().__init__(error_code, message)
        self.operation = operation
        self.error_code = error_code


@runtime_checkable
class WindowsSafetyApi(Protocol):
    """Narrow Win32 safety boundary injected in automated tests."""

    def register_hotkey(
        self,
        window_id: int,
        hotkey_id: int,
        modifiers: int,
        virtual_key: int,
    ) -> bool: ...

    def unregister_hotkey(self, window_id: int, hotkey_id: int) -> bool: ...

    def key_is_down(self, virtual_key: int) -> bool: ...

    def hotkey_message_id(self, message: int) -> int | None: ...

    def last_error(self) -> int: ...


class _POINT(ctypes.Structure):
    _fields_ = (("x", wintypes.LONG), ("y", wintypes.LONG))


class _MSG(ctypes.Structure):
    _fields_ = (
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", _POINT),
        ("lPrivate", wintypes.DWORD),
    )


class CtypesWindowsSafetyApi:
    """ctypes adapter for RegisterHotKey, GetAsyncKeyState, and MSG parsing."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows safety APIs are available only on Windows")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        register: Any = user32.RegisterHotKey
        register.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
        register.restype = wintypes.BOOL
        unregister: Any = user32.UnregisterHotKey
        unregister.argtypes = (wintypes.HWND, ctypes.c_int)
        unregister.restype = wintypes.BOOL
        key_state: Any = user32.GetAsyncKeyState
        key_state.argtypes = (ctypes.c_int,)
        key_state.restype = ctypes.c_short
        self._register = register
        self._unregister = unregister
        self._key_state = key_state

    def register_hotkey(
        self,
        window_id: int,
        hotkey_id: int,
        modifiers: int,
        virtual_key: int,
    ) -> bool:
        return bool(self._register(window_id, hotkey_id, modifiers, virtual_key))

    def unregister_hotkey(self, window_id: int, hotkey_id: int) -> bool:
        return bool(self._unregister(window_id, hotkey_id))

    def key_is_down(self, virtual_key: int) -> bool:
        return bool(int(self._key_state(virtual_key)) & 0x8000)

    def hotkey_message_id(self, message: int) -> int | None:
        if not message:
            return None
        native = ctypes.cast(message, ctypes.POINTER(_MSG)).contents
        if native.message != WM_HOTKEY:
            return None
        return int(native.wParam)

    def last_error(self) -> int:
        return int(ctypes.get_last_error())


@dataclass(frozen=True, slots=True)
class PhysicalInputPreflight:
    """Physical inputs that must be released before live mode can arm."""

    pressed: tuple[str, ...]

    @property
    def clear(self) -> bool:
        return not self.pressed


class _EmergencyNativeEventFilter(QAbstractNativeEventFilter):
    def __init__(self, api: WindowsSafetyApi, callback: Callable[[], None]) -> None:
        super().__init__()
        self._api = api
        self._callback = callback

    def nativeEventFilter(
        self,
        event_type: QByteArray | bytes | bytearray | memoryview,
        message: int,
    ) -> bool:
        raw_type = event_type.data() if isinstance(event_type, QByteArray) else bytes(event_type)
        if raw_type not in {b"windows_generic_MSG", b"windows_dispatcher_MSG"}:
            return False
        if self._api.hotkey_message_id(message) != EMERGENCY_HOTKEY_ID:
            return False
        self._callback()
        return True


class WindowsEmergencyHotkey(QObject):
    """Own one system-wide emergency shortcut for a visible Qt window."""

    triggered = Signal()

    def __init__(
        self,
        *,
        api: WindowsSafetyApi | None = None,
        application: QCoreApplication | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        native_api = api or CtypesWindowsSafetyApi()
        if not isinstance(native_api, WindowsSafetyApi):
            raise TypeError("Expected WindowsSafetyApi")
        app = application or QCoreApplication.instance()
        if app is None:
            raise RuntimeError("A Qt application is required for the emergency hotkey")
        self._api = native_api
        self._application = app
        self._filter = _EmergencyNativeEventFilter(self._api, self.triggered.emit)
        self._window_id: int | None = None

    @property
    def registered(self) -> bool:
        return self._window_id is not None

    def register(self, window_id: int) -> None:
        if isinstance(window_id, bool) or not isinstance(window_id, int) or window_id <= 0:
            raise ValueError("window_id must be a positive integer")
        if self._window_id is not None:
            if self._window_id == window_id:
                return
            raise RuntimeError("Emergency hotkey is already registered for another window")
        self._application.installNativeEventFilter(self._filter)
        if not self._api.register_hotkey(
            window_id,
            EMERGENCY_HOTKEY_ID,
            EMERGENCY_HOTKEY_MODIFIERS,
            EMERGENCY_HOTKEY_VIRTUAL_KEY,
        ):
            self._application.removeNativeEventFilter(self._filter)
            raise WindowsHotkeyError("registration", self._api.last_error())
        self._window_id = window_id

    def close(self) -> None:
        if self._window_id is None:
            return
        window_id = self._window_id
        if not self._api.unregister_hotkey(window_id, EMERGENCY_HOTKEY_ID):
            raise WindowsHotkeyError("cleanup", self._api.last_error())
        self._window_id = None
        self._application.removeNativeEventFilter(self._filter)

    def physical_input_preflight(self) -> PhysicalInputPreflight:
        pressed = tuple(
            label for label, virtual_key in _PREFLIGHT_KEYS if self._api.key_is_down(virtual_key)
        )
        return PhysicalInputPreflight(pressed)


_PREFLIGHT_KEYS = (
    ("left mouse button", 0x01),
    ("right mouse button", 0x02),
    ("middle mouse button", 0x04),
    ("Shift", 0x10),
    ("Ctrl", 0x11),
    ("Alt", 0x12),
    ("left Windows key", 0x5B),
    ("right Windows key", 0x5C),
)
