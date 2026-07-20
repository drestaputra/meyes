"""Shared Windows-safe profile name validation."""

from __future__ import annotations

import re

_INVALID_WINDOWS_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WINDOWS_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


def validate_profile_name(value: object) -> str:
    """Return a normalized Windows-safe profile name or raise ValueError."""
    if not isinstance(value, str):
        raise ValueError("profile name must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("profile name must not be empty")
    if len(normalized) > 80:
        raise ValueError("profile name must contain at most 80 characters")
    if normalized in {".", ".."} or normalized.endswith((".", " ")):
        raise ValueError("profile name is not Windows-safe")
    if _INVALID_WINDOWS_NAME.search(normalized):
        raise ValueError("profile name contains a Windows-reserved character")
    stem = normalized.split(".", 1)[0].upper()
    if stem in _RESERVED_WINDOWS_NAMES:
        raise ValueError("profile name is reserved by Windows")
    return normalized
