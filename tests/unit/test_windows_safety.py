"""Global Windows emergency shortcut and physical preflight tests."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field

import pytest
from PySide6.QtCore import QCoreApplication
from pytestqt.qtbot import QtBot

from meyes.input.windows_safety import (
    EMERGENCY_HOTKEY_ID,
    EMERGENCY_HOTKEY_LABEL,
    EMERGENCY_HOTKEY_MODIFIERS,
    EMERGENCY_HOTKEY_VIRTUAL_KEY,
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    WM_HOTKEY,
    CtypesWindowsSafetyApi,
    WindowsEmergencyHotkey,
    WindowsHotkeyError,
    WindowsSafetyApi,
)


@dataclass(slots=True)
class RecordingWindowsSafetyApi:
    register_success: bool = True
    unregister_success: bool = True
    error_code: int = 0
    pressed_keys: set[int] = field(default_factory=set)
    message_ids: dict[int, int | None] = field(default_factory=dict)
    register_calls: list[tuple[int, int, int, int]] = field(default_factory=list)
    unregister_calls: list[tuple[int, int]] = field(default_factory=list)
    key_queries: list[int] = field(default_factory=list)

    def register_hotkey(
        self,
        window_id: int,
        hotkey_id: int,
        modifiers: int,
        virtual_key: int,
    ) -> bool:
        self.register_calls.append((window_id, hotkey_id, modifiers, virtual_key))
        return self.register_success

    def unregister_hotkey(self, window_id: int, hotkey_id: int) -> bool:
        self.unregister_calls.append((window_id, hotkey_id))
        return self.unregister_success

    def key_is_down(self, virtual_key: int) -> bool:
        self.key_queries.append(virtual_key)
        return virtual_key in self.pressed_keys

    def hotkey_message_id(self, message: int) -> int | None:
        return self.message_ids.get(message)

    def last_error(self) -> int:
        return self.error_code


def _hotkey(qtbot: QtBot, api: RecordingWindowsSafetyApi) -> WindowsEmergencyHotkey:
    del qtbot
    application = QCoreApplication.instance()
    assert application is not None
    return WindowsEmergencyHotkey(api=api, application=application)


def _is_registered(hotkey: WindowsEmergencyHotkey) -> bool:
    return hotkey.registered


def test_emergency_shortcut_avoids_reserved_f12_and_uses_no_repeat() -> None:
    assert EMERGENCY_HOTKEY_LABEL == "Ctrl+Alt+Shift+F11"
    assert EMERGENCY_HOTKEY_VIRTUAL_KEY == 0x7A
    assert EMERGENCY_HOTKEY_VIRTUAL_KEY != 0x7B
    assert EMERGENCY_HOTKEY_MODIFIERS == (MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_NOREPEAT)


def test_registration_is_idempotent_and_close_unregisters(
    qtbot: QtBot,
) -> None:
    api = RecordingWindowsSafetyApi()
    hotkey = _hotkey(qtbot, api)

    hotkey.register(1234)
    hotkey.register(1234)

    assert _is_registered(hotkey)
    assert api.register_calls == [
        (
            1234,
            EMERGENCY_HOTKEY_ID,
            EMERGENCY_HOTKEY_MODIFIERS,
            EMERGENCY_HOTKEY_VIRTUAL_KEY,
        )
    ]
    hotkey.close()
    hotkey.close()
    assert not _is_registered(hotkey)
    assert api.unregister_calls == [(1234, EMERGENCY_HOTKEY_ID)]


def test_registered_native_message_emits_once_and_is_consumed(qtbot: QtBot) -> None:
    api = RecordingWindowsSafetyApi(message_ids={77: EMERGENCY_HOTKEY_ID})
    hotkey = _hotkey(qtbot, api)
    signals: list[str] = []
    hotkey.triggered.connect(lambda: signals.append("emergency"))
    hotkey.register(1234)

    consumed = hotkey._filter.nativeEventFilter(b"windows_generic_MSG", 77)
    ignored_type = hotkey._filter.nativeEventFilter(b"xcb_generic_event_t", 77)
    ignored_message = hotkey._filter.nativeEventFilter(b"windows_dispatcher_MSG", 88)

    assert consumed is True
    assert ignored_type is False
    assert ignored_message is False
    assert signals == ["emergency"]
    hotkey.close()


def test_registration_failure_is_fail_closed_and_retryable(qtbot: QtBot) -> None:
    api = RecordingWindowsSafetyApi(register_success=False, error_code=1409)
    hotkey = _hotkey(qtbot, api)

    with pytest.raises(WindowsHotkeyError) as captured:
        hotkey.register(1234)

    assert captured.value.operation == "registration"
    assert captured.value.error_code == 1409
    assert not _is_registered(hotkey)
    api.register_success = True
    hotkey.register(1234)
    assert _is_registered(hotkey)
    hotkey.close()


def test_cleanup_failure_keeps_filter_and_registration_retryable(qtbot: QtBot) -> None:
    api = RecordingWindowsSafetyApi(unregister_success=False, error_code=5)
    hotkey = _hotkey(qtbot, api)
    hotkey.register(1234)

    with pytest.raises(WindowsHotkeyError) as captured:
        hotkey.close()

    assert captured.value.operation == "cleanup"
    assert _is_registered(hotkey)
    api.unregister_success = True
    hotkey.close()
    assert not _is_registered(hotkey)
    assert api.unregister_calls == [
        (1234, EMERGENCY_HOTKEY_ID),
        (1234, EMERGENCY_HOTKEY_ID),
    ]


@pytest.mark.parametrize("window_id", [0, -1, True, "1234"])
def test_invalid_window_id_never_reaches_native_api(
    qtbot: QtBot,
    window_id: object,
) -> None:
    api = RecordingWindowsSafetyApi()
    hotkey = _hotkey(qtbot, api)

    with pytest.raises(ValueError, match="positive integer"):
        hotkey.register(window_id)  # type: ignore[arg-type]

    assert api.register_calls == []


def test_preflight_reports_physical_buttons_and_modifiers_in_stable_order(
    qtbot: QtBot,
) -> None:
    api = RecordingWindowsSafetyApi(pressed_keys={0x01, 0x11, 0x5C})
    hotkey = _hotkey(qtbot, api)

    preflight = hotkey.physical_input_preflight()

    assert not preflight.clear
    assert preflight.pressed == (
        "left mouse button",
        "Ctrl",
        "right Windows key",
    )
    api.pressed_keys.clear()
    assert hotkey.physical_input_preflight().clear


def test_native_api_loads_without_registering_and_parses_msg_pointer() -> None:
    class Point(ctypes.Structure):
        _fields_ = (("x", wintypes.LONG), ("y", wintypes.LONG))

    class Message(ctypes.Structure):
        _fields_ = (
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", Point),
            ("lPrivate", wintypes.DWORD),
        )

    api = CtypesWindowsSafetyApi()
    message = Message()
    message.message = WM_HOTKEY
    message.wParam = EMERGENCY_HOTKEY_ID

    assert isinstance(api, WindowsSafetyApi)
    assert api.hotkey_message_id(ctypes.addressof(message)) == EMERGENCY_HOTKEY_ID
    message.message = 0
    assert api.hotkey_message_id(ctypes.addressof(message)) is None
    assert api.hotkey_message_id(0) is None
