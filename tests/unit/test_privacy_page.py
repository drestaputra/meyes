"""Privacy page boundary and accessibility tests."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from meyes.ui.live_input import LiveInputState
from meyes.ui.privacy_page import PrivacyPage
from meyes.util.paths import AppPaths


def test_privacy_page_exposes_local_boundaries_and_paths(qtbot: QtBot, tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    page = PrivacyPage(paths)
    qtbot.addWidget(page)

    text = " ".join(label.text() for label in page.findChildren(QLabel))
    assert "not intentionally saved or uploaded" in text
    assert "no OpenAI API call" in text
    assert "Ctrl+Alt+Shift+F11" in text
    assert str(paths.config_file) in text
    assert str(paths.profiles_dir) in text
    assert str(paths.calibration_file) in text
    assert str(paths.log_file) in text


def test_privacy_page_is_read_only_and_starts_safe(qtbot: QtBot, tmp_path: Path) -> None:
    page = PrivacyPage(AppPaths.under(tmp_path))
    qtbot.addWidget(page)

    status = page.findChild(QLabel, "liveInputStatus")
    assert status is not None
    assert "SAFE MODE" in status.text()
    assert status.property("liveInputState") == LiveInputState.SAFE.value
    assert list(tmp_path.iterdir()) == []

    path_labels = page.findChildren(QLabel, "privacyPath")
    assert len(path_labels) == 4
    for label in path_labels:
        assert label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByKeyboard


def test_privacy_page_reflects_armed_and_faulted_state(qtbot: QtBot, tmp_path: Path) -> None:
    page = PrivacyPage(AppPaths.under(tmp_path))
    qtbot.addWidget(page)
    status = page.findChild(QLabel, "liveInputStatus")
    assert status is not None

    page.set_live_input_state(LiveInputState.ARMED)
    assert "LIVE INPUT" in status.text()
    assert status.property("liveInputState") == LiveInputState.ARMED.value

    page.set_live_input_state(LiveInputState.FAULTED)
    assert "FAULT" in status.text()
    assert status.property("liveInputState") == LiveInputState.FAULTED.value
