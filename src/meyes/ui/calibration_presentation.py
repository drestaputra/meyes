"""Distraction-free full-screen presentation for volatile calibration collection."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent, QGuiApplication, QKeyEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from meyes.calibration.session import (
    CALIBRATION_TARGETS,
    CalibrationCaptureStatus,
    CalibrationSessionState,
)
from meyes.ui.calibration_controller import (
    CalibrationController,
    CalibrationFitState,
    calibration_capture_result,
    calibration_fit_outcome,
    calibration_snapshot,
)

_TARGET_SIZE = 32


class CalibrationPresentation(QWidget):
    """Place the active target across the primary screen while collection stays explicit."""

    def __init__(
        self,
        controller: CalibrationController,
        parent: QWidget | None = None,
    ) -> None:
        if not isinstance(controller, CalibrationController):
            raise TypeError("Expected CalibrationController")
        super().__init__(parent, Qt.WindowType.Window)
        self._controller = controller
        self._last_state: CalibrationSessionState | None = None
        self._closing = False
        self.setObjectName("calibrationPresentation")
        self.setWindowTitle("MEYES Calibration")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumSize(640, 480)
        self._build_ui()
        controller.snapshot_changed.connect(self._render_snapshot)
        controller.capture_decided.connect(self._render_capture)
        controller.fit_changed.connect(self._render_fit)
        self._render_snapshot(controller.snapshot)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("calibrationPresentationHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 10, 24, 10)
        self._instruction = QLabel("Calibration is idle")
        self._instruction.setObjectName("calibrationPresentationInstruction")
        self._instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._instruction.setWordWrap(True)
        header_layout.addWidget(self._instruction, stretch=1)

        footer = QFrame()
        footer.setObjectName("calibrationPresentationFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 8, 20, 8)
        footer_layout.setSpacing(10)
        self._progress = QProgressBar()
        self._progress.setObjectName("calibrationPresentationProgress")
        self._progress.setMinimumWidth(180)
        self._feedback = QLabel(
            "Space starts one point · samples collect automatically · Enter advances"
        )
        self._feedback.setObjectName("mutedText")
        self._feedback.setWordWrap(True)
        self._capture_button = QPushButton("Start point · Space")
        self._capture_button.setObjectName("calibrationPresentationCapture")
        self._capture_button.setProperty("primaryAction", True)
        self._next_button = QPushButton("Next · Enter")
        self._next_button.setObjectName("calibrationPresentationNext")
        self._return_button = QPushButton("Return to Calibration")
        self._return_button.setObjectName("calibrationPresentationReturn")
        self._return_button.setProperty("primaryAction", True)
        self._cancel_button = QPushButton("Cancel · Esc")
        self._cancel_button.setObjectName("calibrationPresentationCancel")
        footer_layout.addWidget(self._progress)
        footer_layout.addWidget(self._feedback, stretch=1)
        footer_layout.addWidget(self._capture_button)
        footer_layout.addWidget(self._next_button)
        footer_layout.addWidget(self._return_button)
        footer_layout.addWidget(self._cancel_button)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(32, 32, 32, 32)
        result_row = QHBoxLayout()
        result_row.addStretch(1)
        self._result_panel = QFrame()
        self._result_panel.setObjectName("calibrationResultPanel")
        self._result_panel.setMinimumSize(560, 310)
        self._result_panel.setMaximumWidth(760)
        result_layout = QVBoxLayout(self._result_panel)
        result_layout.setContentsMargins(28, 24, 28, 24)
        result_layout.setSpacing(12)
        result_title = QLabel("Calibration result")
        result_title.setObjectName("panelTitle")
        self._result_status = QLabel("Calculating result")
        self._result_status.setObjectName("calibrationResultStatus")
        self._result_status.setWordWrap(True)
        self._result_status.setAccessibleName("Calibration result status")
        self._result_summary = QLabel("All nine points were collected.")
        self._result_summary.setWordWrap(True)
        self._result_summary.setMinimumHeight(40)
        self._result_metrics = QLabel("Quality evidence is being calculated.")
        self._result_metrics.setObjectName("calibrationResultMetrics")
        self._result_metrics.setWordWrap(True)
        self._result_metrics.setMinimumHeight(88)
        self._result_metrics.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._result_explanation = QLabel(
            "MEYES will explain whether this result can be used for pointer output."
        )
        self._result_explanation.setObjectName("mutedText")
        self._result_explanation.setWordWrap(True)
        self._result_explanation.setMinimumHeight(64)
        result_layout.addWidget(result_title)
        result_layout.addWidget(self._result_status)
        result_layout.addWidget(self._result_summary)
        result_layout.addWidget(self._result_metrics)
        result_layout.addWidget(self._result_explanation)
        result_row.addWidget(self._result_panel, stretch=2)
        result_row.addStretch(1)
        body_layout.addStretch(1)
        body_layout.addLayout(result_row)
        body_layout.addStretch(1)
        self._result_panel.hide()

        layout.addWidget(header)
        layout.addWidget(body, stretch=1)
        layout.addWidget(footer)

        self._target = QLabel("•", self)
        self._target.setObjectName("calibrationFocusTarget")
        self._target.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._target.setFixedSize(_TARGET_SIZE, _TARGET_SIZE)
        self._target.setAccessibleName("Current calibration target")
        self._target.hide()
        self._target.raise_()

        self._capture_button.clicked.connect(self._begin_target)
        self._next_button.clicked.connect(self._advance_or_retry)
        self._return_button.clicked.connect(self._return_to_page)
        self._cancel_button.clicked.connect(self.close)

    def present(self) -> None:
        """Show on the primary screen after the page has safely started collection."""
        if self._controller.snapshot.state is not CalibrationSessionState.AWAITING_TARGET:
            raise RuntimeError("Calibration presentation requires a fresh collection")
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self._position_target()

    @Slot()
    def _begin_target(self) -> None:
        if self._controller.snapshot.state is CalibrationSessionState.AWAITING_TARGET:
            self._controller.begin_target()

    @Slot()
    def _advance_or_retry(self) -> None:
        state = self._controller.snapshot.state
        if state is CalibrationSessionState.TARGET_COMPLETE:
            self._controller.advance()
        elif state is CalibrationSessionState.TARGET_FAILED:
            self._controller.begin_target()

    @Slot()
    def _return_to_page(self) -> None:
        if self._controller.snapshot.state is CalibrationSessionState.COMPLETE:
            self.close()

    @Slot(object)
    def _render_snapshot(self, payload: object) -> None:
        snapshot = calibration_snapshot(payload)
        state = snapshot.state
        target = snapshot.target
        self._target.setVisible(
            target is not None
            and state not in {CalibrationSessionState.COMPLETE, CalibrationSessionState.CANCELLED}
        )
        self._position_target()
        if state is CalibrationSessionState.COMPLETE:
            self._instruction.setText("All 9 points complete · calculating fit evidence")
            self._progress.setRange(0, len(CALIBRATION_TARGETS))
            self._progress.setValue(len(CALIBRATION_TARGETS))
            self._progress.setFormat("9 / 9 points complete")
            self._result_status.setText("Calculating result")
            self._result_status.setProperty("acceptanceState", "pending")
            self._result_summary.setText("All nine points were collected successfully.")
            self._result_metrics.setText("Quality evidence is being calculated.")
            self._result_explanation.setText(
                "MEYES will explain whether this result can be used for pointer output."
            )
        else:
            self._progress.setRange(0, snapshot.samples_per_target)
            self._progress.setValue(snapshot.accepted_for_target)
            self._progress.setFormat(
                f"{snapshot.accepted_for_target} / {snapshot.samples_per_target} accepted"
            )
            if target is None:
                self._instruction.setText(state.value.replace("_", " ").title())
            elif state is CalibrationSessionState.AWAITING_TARGET:
                self._instruction.setText(
                    f"Point {snapshot.target_index + 1} of 9 · Look at {target.label} · press Space"
                )
            elif state is CalibrationSessionState.COLLECTING:
                self._instruction.setText(
                    f"Point {snapshot.target_index + 1} of 9 · Hold steady on {target.label}"
                )
            elif state is CalibrationSessionState.TARGET_COMPLETE:
                self._instruction.setText(
                    f"Point {snapshot.target_index + 1} complete · press Enter"
                )
            else:
                self._instruction.setText(
                    f"Point {snapshot.target_index + 1} needs a retry · press R"
                )
        complete = state is CalibrationSessionState.COMPLETE
        self._result_panel.setVisible(complete)
        self._capture_button.setVisible(not complete)
        self._next_button.setVisible(not complete)
        self._cancel_button.setVisible(not complete)
        self._capture_button.setEnabled(state is CalibrationSessionState.AWAITING_TARGET)
        self._next_button.setEnabled(
            state
            in {CalibrationSessionState.TARGET_COMPLETE, CalibrationSessionState.TARGET_FAILED}
        )
        self._next_button.setText(
            "Retry · R" if state is CalibrationSessionState.TARGET_FAILED else "Next · Enter"
        )
        self._return_button.setVisible(complete)
        self._cancel_button.setEnabled(
            state not in {CalibrationSessionState.IDLE, CalibrationSessionState.CANCELLED}
        )
        if state is not self._last_state:
            transition_messages = {
                CalibrationSessionState.AWAITING_TARGET: (
                    "Look steadily at the target · press Space once to collect stable samples"
                ),
                CalibrationSessionState.COLLECTING: "Collecting samples · hold your gaze steady",
                CalibrationSessionState.TARGET_COMPLETE: "Point complete · press Enter",
                CalibrationSessionState.TARGET_FAILED: "Point needs a retry · press R",
                CalibrationSessionState.COMPLETE: "Calculating volatile fit evidence",
            }
            message = transition_messages.get(state)
            if message is not None:
                self._feedback.setText(message)
        self._last_state = state
        if (
            state in {CalibrationSessionState.IDLE, CalibrationSessionState.CANCELLED}
            and self.isVisible()
            and not self._closing
        ):
            self.close()

    @Slot(object)
    def _render_capture(self, payload: object) -> None:
        result = calibration_capture_result(payload)
        messages = {
            CalibrationCaptureStatus.ACCEPTED: "Sample accepted · keep looking steadily",
            CalibrationCaptureStatus.TARGET_COMPLETE: "Point complete · press Enter",
            CalibrationCaptureStatus.ATTEMPT_LIMIT: "Attempt limit reached · press R to retry",
            CalibrationCaptureStatus.STATISTICAL_OUTLIER: (
                "Outlier rejected · keep looking steadily"
            ),
        }
        self._feedback.setText(
            messages.get(
                result.status,
                f"Rejected: {result.status.value.replace('_', ' ')}",
            )
        )

    @Slot(object)
    def _render_fit(self, payload: object) -> None:
        outcome = calibration_fit_outcome(payload)
        validation = outcome.validation
        self._result_metrics.setText(
            "No usable quality metrics were produced."
            if validation is None
            else (
                "Quality evidence\n"
                f"RMSE: {validation.root_mean_square_error:.4f} · "
                f"Mean error: {validation.mean_error:.4f}\n"
                f"Maximum error: {validation.maximum_error:.4f} · "
                f"Holdout samples: {validation.sample_count}"
            )
        )
        acceptance = outcome.acceptance
        if outcome.state is CalibrationFitState.FAILED:
            state = "Fit failed"
            property_value = "failed"
            summary = "The collected samples could not produce a stable calibration mapper."
        elif acceptance is None:
            state = "Not evaluated"
            property_value = "pending"
            summary = "Calibration quality has not been evaluated."
        else:
            state = acceptance.state.value.replace("_", " ").title()
            property_value = acceptance.state.value
            summaries = {
                "accepted": "This calibration passed every configured evidence limit.",
                "rejected": "This calibration did not pass the configured evidence limits.",
                "review_required": (
                    "A mapper was fitted, but activation is blocked until evidence-backed "
                    "acceptance limits are configured."
                ),
            }
            summary = summaries[property_value]
        self._instruction.setText(f"Calibration complete · {state}")
        self._result_status.setText(state)
        self._result_status.setProperty("acceptanceState", property_value)
        self._result_status.style().unpolish(self._result_status)
        self._result_status.style().polish(self._result_status)
        self._result_summary.setText(summary)
        self._result_explanation.setText(
            f"{outcome.message} Return to Calibration to review details or start again."
        )
        self._feedback.setText(outcome.message)

    def _position_target(self) -> None:
        target = self._controller.snapshot.target
        if target is None:
            return
        x = round(self.width() * target.x - _TARGET_SIZE / 2)
        y = round(self.height() * target.y - _TARGET_SIZE / 2)
        self._target.move(x, y)
        self._target.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_target()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        state = self._controller.snapshot.state
        if event.key() == Qt.Key.Key_Escape:
            if state is CalibrationSessionState.COMPLETE:
                self._return_to_page()
            else:
                self.close()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Space and state is CalibrationSessionState.AWAITING_TARGET:
            self._begin_target()
            event.accept()
            return
        if (
            event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
            and state is CalibrationSessionState.TARGET_COMPLETE
        ):
            self._advance_or_retry()
            event.accept()
            return
        if event.key() == Qt.Key.Key_R and state is CalibrationSessionState.TARGET_FAILED:
            self._advance_or_retry()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing:
            event.accept()
            return
        self._closing = True
        state = self._controller.snapshot.state
        if state not in {
            CalibrationSessionState.IDLE,
            CalibrationSessionState.CANCELLED,
            CalibrationSessionState.COMPLETE,
        }:
            self._controller.cancel()
        self._closing = False
        event.accept()
