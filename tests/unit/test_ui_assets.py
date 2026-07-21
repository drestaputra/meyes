"""Application icon packaging and safe fallback tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from meyes.ui import assets
from meyes.ui.assets import application_icon, application_icon_path


def test_application_icon_is_present_and_loadable(qtbot: QtBot) -> None:
    del qtbot
    path = application_icon_path()

    assert path.name == "meyes.svg"
    assert path.stat().st_size > 0
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "ba44e15e0eacf011dbcbf978364cf8f64d2a8d93d477810de54efa86417508a8"
    )
    assert not application_icon().isNull()


def test_packaged_icon_is_preferred_over_source_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packaged = tmp_path / "packaged"
    source = tmp_path / "source"
    packaged.mkdir()
    source.mkdir()
    packaged_icon = packaged / assets.APPLICATION_ICON_FILENAME
    source_icon = source / assets.APPLICATION_ICON_FILENAME
    packaged_icon.write_text("packaged", encoding="utf-8")
    source_icon.write_text("source", encoding="utf-8")
    monkeypatch.setattr(assets, "_PACKAGED_ICONS_DIR", packaged)
    monkeypatch.setattr(assets, "_SOURCE_ICONS_DIR", source)

    assert application_icon_path() == packaged_icon


def test_missing_icon_uses_native_null_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qtbot: QtBot
) -> None:
    del qtbot
    monkeypatch.setattr(assets, "_PACKAGED_ICONS_DIR", tmp_path / "packaged")
    monkeypatch.setattr(assets, "_SOURCE_ICONS_DIR", tmp_path / "source")

    with pytest.raises(FileNotFoundError, match="application icon"):
        application_icon_path()
    assert application_icon().isNull()
