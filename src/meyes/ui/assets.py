"""Resolve and load small packaged UI assets with source-tree fallback."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

APPLICATION_ICON_FILENAME = "meyes.svg"
_PACKAGED_ICONS_DIR = Path(__file__).resolve().parents[1] / "resources" / "icons"
_SOURCE_ICONS_DIR = Path(__file__).resolve().parents[3] / "resources" / "icons"


def application_icon_path() -> Path:
    """Return the packaged icon or the development source-tree fallback."""
    candidates = (
        _PACKAGED_ICONS_DIR / APPLICATION_ICON_FILENAME,
        _SOURCE_ICONS_DIR / APPLICATION_ICON_FILENAME,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"MEYES application icon not found. Searched: {searched}")


def application_icon() -> QIcon:
    """Load the optional window icon while allowing safe fallback to the native default."""
    try:
        path = application_icon_path()
    except OSError:
        return QIcon()
    return QIcon(str(path))
