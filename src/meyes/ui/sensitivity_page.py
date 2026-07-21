"""Validated cursor smoothing and movement-gate settings view."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from meyes.config.models import CursorSettings


@dataclass(frozen=True, slots=True)
class SensitivitySaveResult:
    """Outcome returned by the composition root after a save attempt."""

    applied: bool
    message: str
    settings: CursorSettings
    warning: bool = False


SaveSensitivity = Callable[[CursorSettings], SensitivitySaveResult]


class SensitivityPage(QWidget):
    """Edit validated cursor behavior without exposing an output-arm control."""

    def __init__(
        self,
        settings: CursorSettings,
        save_settings: SaveSensitivity,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(settings, CursorSettings):
            raise TypeError("Expected CursorSettings")
        if not callable(save_settings):
            raise TypeError("save_settings must be callable")
        self._settings = settings
        self._save_settings = save_settings
        self.setObjectName("sensitivityPage")
        self._build_ui()
        self._render(settings)

    def _build_ui(self) -> None:
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("sensitivityScroll")
        scroll.viewport().setObjectName("sensitivityViewport")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("sensitivityContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title = QLabel("Sensitivity")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Tune the accepted gaze cursor's adaptive smoothing and conservative temple gate. "
            "These values do not change calibration acceptance and cannot arm operating-system "
            "input."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        safety = QLabel(
            "SAVE SAFETY · Saving releases Live Input first and rebuilds only a still-valid "
            "accepted cursor pipeline"
        )
        safety.setObjectName("safeBanner")
        safety.setWordWrap(True)
        self._feedback = QLabel()
        self._feedback.setObjectName("sensitivityFeedback")
        self._feedback.setWordWrap(True)
        self._feedback.hide()
        self._dirty_status = QLabel("Saved settings · no pending changes")
        self._dirty_status.setObjectName("sensitivityDirtyStatus")
        self._dirty_status.setProperty("draftState", "clean")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(safety)
        layout.addWidget(self._feedback)
        layout.addWidget(self._build_smoothing_panel())
        layout.addWidget(self._build_gate_panel())
        layout.addWidget(self._dirty_status)

        actions = QHBoxLayout()
        self._reset_button = QPushButton("Stage defaults")
        self._reset_button.setObjectName("sensitivityResetButton")
        self._save_button = QPushButton("Save sensitivity")
        self._save_button.setObjectName("sensitivitySaveButton")
        self._save_button.setProperty("primaryAction", True)
        actions.addWidget(self._reset_button)
        actions.addStretch(1)
        actions.addWidget(self._save_button)
        layout.addLayout(actions)
        layout.addStretch(1)

        scroll.setWidget(content)
        page_layout.addWidget(scroll)

        for input_widget in (
            self._minimum_cutoff,
            self._speed_coefficient,
            self._derivative_cutoff,
            self._maximum_gap,
            self._resume_delay,
        ):
            input_widget.valueChanged.connect(self._update_controls)
        self._freeze_during_temple.stateChanged.connect(self._update_controls)
        self._reset_button.clicked.connect(self._stage_defaults)
        self._save_button.clicked.connect(self._save)

    def _build_smoothing_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        heading = QLabel("Adaptive smoothing")
        heading.setObjectName("panelTitle")
        help_text = QLabel(
            "Higher minimum cutoff follows motion more directly. Higher speed response reduces "
            "smoothing during fast movement. Maximum gap resets stale filter history."
        )
        help_text.setObjectName("mutedText")
        help_text.setWordWrap(True)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._minimum_cutoff = self._double_input("minimumCutoffInput", 0.000001, 1_000_000)
        self._speed_coefficient = self._double_input("speedCoefficientInput", 0.0, 1_000_000)
        self._derivative_cutoff = self._double_input("derivativeCutoffInput", 0.000001, 1_000_000)
        self._maximum_gap = QSpinBox()
        self._maximum_gap.setObjectName("maximumGapInput")
        self._maximum_gap.setRange(50, 5000)
        self._maximum_gap.setSuffix(" ms")

        form.addRow("Minimum cutoff", self._minimum_cutoff)
        form.addRow("Speed response", self._speed_coefficient)
        form.addRow("Derivative cutoff", self._derivative_cutoff)
        form.addRow("Stale reset gap", self._maximum_gap)
        layout.addWidget(heading)
        layout.addWidget(help_text)
        layout.addLayout(form)
        return panel

    def _build_gate_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        heading = QLabel("Temple movement gate")
        heading.setObjectName("panelTitle")
        help_text = QLabel(
            "Tracking loss always suspends movement. The option below additionally freezes gaze "
            "movement during temple taps/holds and delays resume after release."
        )
        help_text.setObjectName("mutedText")
        help_text.setWordWrap(True)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._freeze_during_temple = QCheckBox("Freeze during temple gestures")
        self._freeze_during_temple.setObjectName("freezeDuringTempleInput")
        self._resume_delay = QSpinBox()
        self._resume_delay.setObjectName("resumeDelayInput")
        self._resume_delay.setRange(0, 5000)
        self._resume_delay.setSuffix(" ms")
        form.addRow("Gesture freeze", self._freeze_during_temple)
        form.addRow("Resume delay", self._resume_delay)
        layout.addWidget(heading)
        layout.addWidget(help_text)
        layout.addLayout(form)
        return panel

    @staticmethod
    def _double_input(object_name: str, minimum: float, maximum: float) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setObjectName(object_name)
        field.setDecimals(6)
        field.setRange(minimum, maximum)
        field.setSingleStep(0.01)
        return field

    def _draft(self) -> CursorSettings:
        return CursorSettings(
            minimum_cutoff=self._minimum_cutoff.value(),
            speed_coefficient=self._speed_coefficient.value(),
            derivative_cutoff=self._derivative_cutoff.value(),
            maximum_gap_ms=self._maximum_gap.value(),
            freeze_during_temple_gesture=self._freeze_during_temple.isChecked(),
            resume_delay_ms=self._resume_delay.value(),
        )

    def _render(self, settings: CursorSettings) -> None:
        blockers = [
            QSignalBlocker(widget)
            for widget in (
                self._minimum_cutoff,
                self._speed_coefficient,
                self._derivative_cutoff,
                self._maximum_gap,
                self._freeze_during_temple,
                self._resume_delay,
            )
        ]
        self._minimum_cutoff.setValue(settings.minimum_cutoff)
        self._speed_coefficient.setValue(settings.speed_coefficient)
        self._derivative_cutoff.setValue(settings.derivative_cutoff)
        self._maximum_gap.setValue(settings.maximum_gap_ms)
        self._freeze_during_temple.setChecked(settings.freeze_during_temple_gesture)
        self._resume_delay.setValue(settings.resume_delay_ms)
        del blockers
        self._update_controls()

    def _update_controls(self, *_args: object) -> None:
        dirty = self._draft() != self._settings
        self._save_button.setEnabled(dirty)
        self._dirty_status.setText(
            "Unsaved sensitivity changes" if dirty else "Saved settings · no pending changes"
        )
        self._dirty_status.setProperty("draftState", "dirty" if dirty else "clean")
        self._dirty_status.style().unpolish(self._dirty_status)
        self._dirty_status.style().polish(self._dirty_status)

    def _stage_defaults(self) -> None:
        self._render(CursorSettings())
        self._show_feedback(
            "Defaults are staged. Select Save sensitivity to apply them.", "warning"
        )

    def _save(self) -> None:
        draft = self._draft()
        result = self._save_settings(draft)
        if not isinstance(result, SensitivitySaveResult):
            raise TypeError("save_settings returned an invalid result")
        if result.applied:
            self._settings = result.settings
            self._render(result.settings)
            self._show_feedback(result.message, "warning" if result.warning else "success")
        else:
            self._show_feedback(result.message, "error")

    def _show_feedback(self, message: str, status: str) -> None:
        self._feedback.setText(message)
        self._feedback.setProperty("feedbackStatus", status)
        self._feedback.style().unpolish(self._feedback)
        self._feedback.style().polish(self._feedback)
        self._feedback.show()
