"""Read-only DPI-aware Windows primary-monitor geometry acquisition."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import Any, Protocol, runtime_checkable

from meyes.cursor.screen_mapping import PhysicalScreenGeometry

_MONITOR_DEFAULTTOPRIMARY = 1
_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4


class WindowsScreenGeometryError(OSError):
    """Report a bounded native geometry operation failure."""

    def __init__(self, operation: str, error_code: int) -> None:
        message = f"Windows screen geometry {operation} failed"
        if error_code:
            message = f"{message}; Windows error {error_code}"
        else:
            message = f"{message}; Windows did not report a specific cause"
        super().__init__(error_code, message)
        self.operation = operation
        self.error_code = error_code


@runtime_checkable
class WindowsScreenGeometryApi(Protocol):
    """Narrow temporary-DPI-scope boundary injected by unit tests."""

    def enter_physical_pixel_scope(self) -> object: ...

    def primary_monitor_rect(self) -> tuple[int, int, int, int]: ...

    def restore_dpi_scope(self, previous_context: object) -> None: ...


class _POINT(ctypes.Structure):
    _fields_ = (("x", wintypes.LONG), ("y", wintypes.LONG))


class _RECT(ctypes.Structure):
    _fields_ = (
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    )


class _MONITORINFO(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wintypes.DWORD),
    )


class CtypesWindowsScreenGeometryApi:
    """User32 adapter that only reads monitor geometry in a temporary DPI scope."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows screen geometry is available only on Windows")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        try:
            set_thread_context: Any = user32.SetThreadDpiAwarenessContext
            monitor_from_point: Any = user32.MonitorFromPoint
            get_monitor_info: Any = user32.GetMonitorInfoW
        except AttributeError as error:
            raise OSError("Required Windows DPI APIs are unavailable") from error

        set_thread_context.argtypes = (ctypes.c_void_p,)
        set_thread_context.restype = ctypes.c_void_p
        monitor_from_point.argtypes = (_POINT, wintypes.DWORD)
        monitor_from_point.restype = wintypes.HANDLE
        get_monitor_info.argtypes = (wintypes.HANDLE, ctypes.POINTER(_MONITORINFO))
        get_monitor_info.restype = wintypes.BOOL

        self._set_thread_context = set_thread_context
        self._monitor_from_point = monitor_from_point
        self._get_monitor_info = get_monitor_info

    def enter_physical_pixel_scope(self) -> object:
        ctypes.set_last_error(0)
        previous = self._set_thread_context(
            ctypes.c_void_p(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        )
        if not previous:
            raise WindowsScreenGeometryError("DPI-scope entry", ctypes.get_last_error())
        return int(previous)

    def primary_monitor_rect(self) -> tuple[int, int, int, int]:
        ctypes.set_last_error(0)
        monitor = self._monitor_from_point(_POINT(0, 0), _MONITOR_DEFAULTTOPRIMARY)
        if not monitor:
            raise WindowsScreenGeometryError("primary-monitor lookup", ctypes.get_last_error())
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not self._get_monitor_info(monitor, ctypes.byref(info)):
            raise WindowsScreenGeometryError("primary-monitor read", ctypes.get_last_error())
        rect = info.rcMonitor
        return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)

    def restore_dpi_scope(self, previous_context: object) -> None:
        if isinstance(previous_context, bool) or not isinstance(previous_context, int):
            raise TypeError("Previous DPI context must be an integer pointer value")
        ctypes.set_last_error(0)
        restored = self._set_thread_context(ctypes.c_void_p(previous_context))
        if not restored:
            raise WindowsScreenGeometryError("DPI-scope restoration", ctypes.get_last_error())


class WindowsPrimaryScreenGeometryProvider:
    """Return primary-screen physical pixels or fail without a partial result."""

    def __init__(
        self,
        api: WindowsScreenGeometryApi | None = None,
        *,
        platform_name: str | None = None,
    ) -> None:
        selected_platform = os.name if platform_name is None else platform_name
        if api is None:
            if selected_platform != "nt":
                raise OSError("Windows screen geometry is available only on Windows")
            api = CtypesWindowsScreenGeometryApi()
        if not isinstance(api, WindowsScreenGeometryApi):
            raise TypeError("Expected WindowsScreenGeometryApi")
        self._api = api

    def read(self) -> PhysicalScreenGeometry:
        previous_context = self._api.enter_physical_pixel_scope()
        try:
            rect = self._api.primary_monitor_rect()
        finally:
            self._api.restore_dpi_scope(previous_context)
        left, top, right, bottom = _validated_rect(rect)
        return PhysicalScreenGeometry(left, top, right - left, bottom - top)


def _validated_rect(rect: object) -> tuple[int, int, int, int]:
    if not isinstance(rect, tuple) or len(rect) != 4:
        raise TypeError("Primary monitor rectangle must contain four integers")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in rect):
        raise TypeError("Primary monitor rectangle must contain four integers")
    left, top, right, bottom = rect
    if right <= left or bottom <= top:
        raise ValueError("Primary monitor rectangle must have positive dimensions")
    return left, top, right, bottom
