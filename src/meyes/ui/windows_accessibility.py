"""Read-only Windows accessibility preference probes."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import Any, Protocol, runtime_checkable

_SPI_GETHIGHCONTRAST = 0x0042
_HCF_HIGHCONTRASTON = 0x00000001


class _HIGHCONTRASTW(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.UINT),
        ("dwFlags", wintypes.DWORD),
        ("lpszDefaultScheme", wintypes.LPWSTR),
    )


@runtime_checkable
class WindowsAccessibilityApi(Protocol):
    """Narrow read-only accessibility boundary injected in tests."""

    def high_contrast_enabled(self) -> bool: ...


class CtypesWindowsAccessibilityApi:
    """Read the Windows High Contrast flag without changing system preferences."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows accessibility preferences are available only on Windows")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        system_parameters_info: Any = user32.SystemParametersInfoW
        system_parameters_info.argtypes = (
            wintypes.UINT,
            wintypes.UINT,
            ctypes.c_void_p,
            wintypes.UINT,
        )
        system_parameters_info.restype = wintypes.BOOL
        self._system_parameters_info = system_parameters_info

    def high_contrast_enabled(self) -> bool:
        preference = _HIGHCONTRASTW()
        preference.cbSize = ctypes.sizeof(_HIGHCONTRASTW)
        ctypes.set_last_error(0)
        if not self._system_parameters_info(
            _SPI_GETHIGHCONTRAST,
            preference.cbSize,
            ctypes.byref(preference),
            0,
        ):
            error_code = ctypes.get_last_error()
            raise OSError(error_code, "Windows High Contrast preference read failed")
        return bool(int(preference.dwFlags) & _HCF_HIGHCONTRASTON)


def windows_high_contrast_enabled(api: WindowsAccessibilityApi | None = None) -> bool:
    """Return the read-only flag, falling back to normal theme when detection is unavailable."""

    try:
        native_api = api or CtypesWindowsAccessibilityApi()
        if not isinstance(native_api, WindowsAccessibilityApi):
            raise TypeError("Expected WindowsAccessibilityApi")
        return native_api.high_contrast_enabled()
    except OSError:
        return False
