"""Safe first-run orientation tests."""

from __future__ import annotations

from typing import TypeVar
from unittest.mock import patch

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from meyes.ui.first_run_wizard import FirstRunWizard

QObjectType = TypeVar("QObjectType", bound=QObject)


def _child(wizard: FirstRunWizard, widget_type: type[QObjectType], name: str) -> QObjectType:
    widget = wizard.findChild(widget_type, name)
    assert widget is not None
    return widget


def _advance_to_final(wizard: FirstRunWizard) -> None:
    next_button = _child(wizard, QPushButton, "firstRunNextButton")
    next_button.click()
    next_button.click()


def test_first_run_requires_final_safety_dialog_confirmation(qtbot: QtBot) -> None:
    completions = 0

    def complete() -> bool:
        nonlocal completions
        completions += 1
        return True

    wizard = FirstRunWizard(complete)
    qtbot.addWidget(wizard)

    assert wizard.current_step == 0
    assert _child(wizard, QPushButton, "firstRunBackButton").isEnabled() is False
    assert _child(wizard, QPushButton, "firstRunFinishButton").isHidden() is True
    _advance_to_final(wizard)
    finish = _child(wizard, QPushButton, "firstRunFinishButton")

    assert wizard.current_step == 2
    assert finish.isHidden() is False
    assert finish.isEnabled() is True
    assert wizard.findChild(QWidget, "firstRunSafetyAcknowledgement") is None

    with patch("meyes.ui.first_run_wizard.confirm_action", return_value=False):
        finish.click()
    assert completions == 0
    assert wizard.result() == 0

    with patch("meyes.ui.first_run_wizard.confirm_action", return_value=True) as confirm:
        finish.click()

    assert completions == 1
    assert confirm.call_args.kwargs["confirm_label"] == "Finish setup"
    assert wizard.result() == QDialog.DialogCode.Accepted


def test_not_now_does_not_mark_setup_complete(qtbot: QtBot) -> None:
    completions = 0

    def complete() -> bool:
        nonlocal completions
        completions += 1
        return True

    wizard = FirstRunWizard(complete)
    qtbot.addWidget(wizard)

    _child(wizard, QPushButton, "firstRunNotNowButton").click()

    assert completions == 0
    assert wizard.result() == QDialog.DialogCode.Rejected


def test_persistence_failure_keeps_wizard_open_and_safe(qtbot: QtBot) -> None:
    wizard = FirstRunWizard(lambda: False)
    qtbot.addWidget(wizard)
    _advance_to_final(wizard)

    with patch("meyes.ui.first_run_wizard.confirm_action", return_value=True):
        _child(wizard, QPushButton, "firstRunFinishButton").click()

    assert wizard.result() == 0
    feedback = _child(wizard, QLabel, "firstRunFeedback")
    assert feedback.isHidden() is False
    assert "remains in Safe Mode" in feedback.text()
