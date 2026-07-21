"""Modal confirmation dialog safety tests."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from meyes.ui.confirmation_dialog import confirm_action


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
