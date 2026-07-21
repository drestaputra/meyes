"""Application icon packaging and safe fallback tests."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from meyes.ui import assets
from meyes.ui.assets import application_icon, application_icon_path

WINDOWS_ICON_PATH = Path(__file__).resolve().parents[2] / "resources" / "icons" / "meyes.ico"


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


def test_windows_icon_contains_every_generated_png_frame() -> None:
    content = WINDOWS_ICON_PATH.read_bytes()
    reserved, image_type, count = struct.unpack_from("<HHH", content)

    assert (reserved, image_type, count) == (0, 1, 10)
    assert len(content) == 19_906
    assert (
        hashlib.sha256(content).hexdigest()
        == "64f9ad51118096b8103b8c2cefc7931d3fc4d196e92d59c70968ac8d9a8b48a9"
    )
    sizes: list[int] = []
    for index in range(count):
        width, height, colors, entry_reserved, planes, bit_count, length, offset = (
            struct.unpack_from("<BBBBHHII", content, 6 + index * 16)
        )
        normalized_width = width or 256
        normalized_height = height or 256
        assert normalized_width == normalized_height
        assert (colors, entry_reserved, planes, bit_count) == (0, 0, 1, 32)
        assert content[offset : offset + 8] == b"\x89PNG\r\n\x1a\n"
        assert offset + length <= len(content)
        sizes.append(normalized_width)
    assert sizes == [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


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
