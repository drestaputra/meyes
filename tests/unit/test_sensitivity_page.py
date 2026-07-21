"""Sensitivity settings view tests."""

from __future__ import annotations

from typing import TypeVar

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QLabel, QPushButton, QSpinBox
from pytestqt.qtbot import QtBot

from meyes.config.models import CursorSettings
from meyes.ui.sensitivity_page import SensitivityPage, SensitivitySaveResult

QObjectType = TypeVar("QObjectType", bound=QObject)


def _child(page: SensitivityPage, widget_type: type[QObjectType], name: str) -> QObjectType:
    widget = page.findChild(widget_type, name)
    assert widget is not None
    return widget


def test_sensitivity_page_starts_clean_with_validated_values(qtbot: QtBot) -> None:
    settings = CursorSettings(
        minimum_cutoff=1.5,
        speed_coefficient=0.2,
        derivative_cutoff=2.0,
        maximum_gap_ms=400,
        freeze_during_temple_gesture=False,
        resume_delay_ms=300,
    )
    page = SensitivityPage(
        settings,
        lambda draft: SensitivitySaveResult(True, "saved", draft),
    )
    qtbot.addWidget(page)

    assert _child(page, QDoubleSpinBox, "minimumCutoffInput").value() == 1.5
    assert _child(page, QDoubleSpinBox, "speedCoefficientInput").value() == 0.2
    assert _child(page, QDoubleSpinBox, "derivativeCutoffInput").value() == 2.0
    assert _child(page, QSpinBox, "maximumGapInput").value() == 400
    assert _child(page, QCheckBox, "freezeDuringTempleInput").isChecked() is False
    assert _child(page, QSpinBox, "resumeDelayInput").value() == 300
    assert _child(page, QPushButton, "sensitivitySaveButton").isEnabled() is False


def test_save_passes_complete_settings_and_returns_clean(qtbot: QtBot) -> None:
    calls: list[CursorSettings] = []

    def save(settings: CursorSettings) -> SensitivitySaveResult:
        calls.append(settings)
        return SensitivitySaveResult(True, "Settings saved safely.", settings)

    page = SensitivityPage(CursorSettings(), save)
    qtbot.addWidget(page)
    _child(page, QDoubleSpinBox, "minimumCutoffInput").setValue(2.5)
    _child(page, QSpinBox, "resumeDelayInput").setValue(450)
    save_button = _child(page, QPushButton, "sensitivitySaveButton")

    assert save_button.isEnabled() is True
    save_button.click()

    assert len(calls) == 1
    assert calls[0].minimum_cutoff == 2.5
    assert calls[0].resume_delay_ms == 450
    assert save_button.isEnabled() is False
    feedback = _child(page, QLabel, "sensitivityFeedback")
    assert feedback.text() == "Settings saved safely."
    assert feedback.property("feedbackStatus") == "success"


def test_failed_save_retains_dirty_draft(qtbot: QtBot) -> None:
    current = CursorSettings()
    page = SensitivityPage(
        current,
        lambda draft: SensitivitySaveResult(False, "Release failed.", current),
    )
    qtbot.addWidget(page)
    _child(page, QSpinBox, "maximumGapInput").setValue(800)
    save_button = _child(page, QPushButton, "sensitivitySaveButton")

    save_button.click()

    assert save_button.isEnabled() is True
    assert _child(page, QSpinBox, "maximumGapInput").value() == 800
    feedback = _child(page, QLabel, "sensitivityFeedback")
    assert feedback.text() == "Release failed."
    assert feedback.property("feedbackStatus") == "error"


def test_stage_defaults_does_not_save_automatically(qtbot: QtBot) -> None:
    calls: list[CursorSettings] = []

    def save(settings: CursorSettings) -> SensitivitySaveResult:
        calls.append(settings)
        return SensitivitySaveResult(True, "saved", settings)

    page = SensitivityPage(
        CursorSettings(minimum_cutoff=4.0),
        save,
    )
    qtbot.addWidget(page)

    _child(page, QPushButton, "sensitivityResetButton").click()

    assert calls == []
    assert _child(page, QDoubleSpinBox, "minimumCutoffInput").value() == 1.0
    assert _child(page, QPushButton, "sensitivitySaveButton").isEnabled() is True
    assert "staged" in _child(page, QLabel, "sensitivityFeedback").text()
