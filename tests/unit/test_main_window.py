"""Application shell smoke tests."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from meyes.config.models import AppConfig
from meyes.ui.main_window import MainWindow


def test_main_window_has_accessible_application_shell(qtbot: QtBot) -> None:
    window = MainWindow(AppConfig())
    qtbot.addWidget(window)

    assert window.windowTitle() == "Meyes"
    assert window.minimumWidth() == 900
    assert window.minimumHeight() == 640
