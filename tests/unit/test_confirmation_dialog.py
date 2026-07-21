"""Modal confirmation dialog safety tests."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from meyes.ui.confirmation_dialog import confirm_action
from meyes.ui.theme import ThemeTokens, build_stylesheet


def _interact_with_dialog(
    qtbot: QtBot,
    action: Callable[[QPushButton, QPushButton], None],
) -> None:
    dialog = QApplication.activeModalWidget()
    assert isinstance(dialog, QMessageBox)
    confirm_button = dialog.findChild(QPushButton, "confirmActionButton")
    cancel_button = dialog.findChild(QPushButton, "cancelActionButton")
    assert confirm_button is not None and cancel_button is not None
    assert dialog.defaultButton() is cancel_button
    assert dialog.escapeButton() is cancel_button
    action(confirm_button, cancel_button)
    qtbot.waitUntil(lambda: not dialog.isVisible(), timeout=1000)


def test_confirmation_dialog_defaults_to_cancel(qtbot: QtBot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    QTimer.singleShot(
        0,
        lambda: _interact_with_dialog(
            qtbot,
            lambda _confirm, cancel: cancel.click(),
        ),
    )

    accepted = confirm_action(
        parent,
        title="Delete item?",
        message="This action cannot be undone.",
        confirm_label="Delete permanently",
        destructive=True,
    )

    assert not accepted


def test_confirmation_dialog_returns_true_only_for_action_button(qtbot: QtBot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    QTimer.singleShot(
        0,
        lambda: _interact_with_dialog(
            qtbot,
            lambda confirm, _cancel: confirm.click(),
        ),
    )

    accepted = confirm_action(
        parent,
        title="Restore item?",
        message="The item will be revalidated.",
        confirm_label="Restore",
    )

    assert accepted


def test_confirmation_dialog_text_contrasts_with_app_theme(qtbot: QtBot) -> None:
    parent = QWidget()
    parent.setStyleSheet(build_stylesheet())
    qtbot.addWidget(parent)
    tokens = ThemeTokens()

    def inspect_theme(_confirm: QPushButton, cancel: QPushButton) -> None:
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        message = dialog.findChild(QLabel, "qt_msgbox_label")
        assert message is not None
        assert (
            dialog.palette().color(QPalette.ColorRole.Window).name().casefold()
            == tokens.surface.casefold()
        )
        assert (
            message.palette().color(QPalette.ColorRole.WindowText).name().casefold()
            == tokens.ink.casefold()
        )
        assert (
            cancel.palette().color(QPalette.ColorRole.ButtonText).name().casefold()
            == tokens.ink.casefold()
        )
        cancel.click()

    QTimer.singleShot(
        0,
        lambda: _interact_with_dialog(qtbot, inspect_theme),
    )

    accepted = confirm_action(
        parent,
        title="Forget calibration?",
        message="This message must remain readable under the app theme.",
        confirm_label="Forget calibration",
        destructive=True,
    )

    assert not accepted
