"""Interactive full-screen smooth-pursuit calibration presentation."""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, QTimer, Slot
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
    CalibrationCaptureStatus,
    CalibrationSessionState,
    PursuitAttentionState,
    PursuitTargetPosition,
)
from meyes.ui.calibration_controller import (
    CalibrationController,
    CalibrationFitState,
    calibration_capture_result,
    calibration_fit_outcome,
    calibration_snapshot,
)

_TARGET_SIZE = 44
_COUNTDOWN_SECONDS = 3.0
_PIPELINE_DRAIN_SECONDS = 0.5


class CalibrationPresentation(QWidget):
    """Animate one synchronized target while camera samples arrive automatically."""

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
        self._last_position: PursuitTargetPosition | None = None
        self._countdown_started_at: float | None = None
        self._finish_deadline: float | None = None
        self._closing = False
        self.setObjectName("calibrationPresentation")
        self.setWindowTitle("MEYES Smooth Pursuit Calibration")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumSize(640, 480)
        self._build_ui()
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(16)
        self._animation_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._animation_timer.timeout.connect(self._animate)
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
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 10, 24, 10)
        header_layout.setSpacing(4)
        self._instruction = QLabel("Smooth Pursuit calibration is idle")
        self._instruction.setObjectName("calibrationPresentationInstruction")
        self._instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._instruction.setWordWrap(True)
        self._quality = QLabel("Camera signal is waiting")
        self._quality.setObjectName("calibrationPursuitQuality")
        self._quality.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quality.setWordWrap(True)
        self._quality.setAccessibleName("Live pursuit tracking quality")
        header_layout.addWidget(self._instruction)
        header_layout.addWidget(self._quality)

        footer = QFrame()
        footer.setObjectName("calibrationPresentationFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 8, 20, 8)
        footer_layout.setSpacing(10)
        self._progress = QProgressBar()
        self._progress.setObjectName("calibrationPresentationProgress")
        self._progress.setRange(0, 1000)
        self._progress.setMinimumWidth(260)
        self._progress.setAccessibleName("Smooth pursuit sweep progress")
        self._feedback = QLabel(
            "Keep your head still and follow the blue target with only your eyes"
        )
        self._feedback.setObjectName("mutedText")
        self._feedback.setWordWrap(True)
        self._retry_button = QPushButton("Retry live sweep · R")
        self._retry_button.setObjectName("calibrationPresentationRetry")
        self._retry_button.setProperty("primaryAction", True)
        self._return_button = QPushButton("Return to Calibration")
        self._return_button.setObjectName("calibrationPresentationReturn")
        self._return_button.setProperty("primaryAction", True)
        self._cancel_button = QPushButton("Cancel · Esc")
        self._cancel_button.setObjectName("calibrationPresentationCancel")
        footer_layout.addWidget(self._progress)
        footer_layout.addWidget(self._feedback, stretch=1)
        footer_layout.addWidget(self._retry_button)
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
        self._result_summary = QLabel("The live sweep is being evaluated.")
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

        self._target = QLabel("●", self)
        self._target.setObjectName("calibrationFocusTarget")
        self._target.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._target.setFixedSize(_TARGET_SIZE, _TARGET_SIZE)
        self._target.setAccessibleName("Moving smooth pursuit target")
        self._target.setAccessibleDescription(
            "Follow this target continuously with your eyes while keeping your head still"
        )
        self._target.hide()
        self._target.raise_()

        self._retry_button.clicked.connect(self._retry)
        self._return_button.clicked.connect(self._return_to_page)
        self._cancel_button.clicked.connect(self.close)

    def present(self) -> None:
        """Show full-screen and begin a hands-free countdown."""

        if self._controller.snapshot.state is not CalibrationSessionState.AWAITING_TARGET:
            raise RuntimeError("Calibration presentation requires a fresh collection")
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self._begin_countdown()

    def _begin_countdown(self) -> None:
        self._countdown_started_at = self._controller.now()
        self._finish_deadline = None
        self._last_position = self._controller.pursuit_position()
        self._result_panel.hide()
        self._retry_button.hide()
        self._return_button.hide()
        self._cancel_button.show()
        self._target.show()
        self._position_target(self._last_position)
        self._animation_timer.start()
        self._animate()

    @Slot()
    def _retry(self) -> None:
        if self._controller.snapshot.state is CalibrationSessionState.TARGET_FAILED:
            self._begin_countdown()

    @Slot()
    def _return_to_page(self) -> None:
        if self._controller.snapshot.state is CalibrationSessionState.COMPLETE:
            self.close()

    @Slot()
    def _animate(self) -> None:
        now = self._controller.now()
        if self._countdown_started_at is not None:
            elapsed = max(0.0, now - self._countdown_started_at)
            remaining = max(0, math.ceil(_COUNTDOWN_SECONDS - elapsed))
            self._instruction.setText(
                "Look at the blue target · live capture starts now"
                if remaining == 0
                else f"Get ready · live capture starts in {remaining}"
            )
            self._quality.setText("Both eyes should remain visible · keep your head still")
            self._progress.setValue(0)
            self._progress.setFormat("Preparing live sweep")
            if elapsed < _COUNTDOWN_SECONDS:
                return
            self._countdown_started_at = None
            self._controller.begin_target()

        if self._controller.snapshot.state is not CalibrationSessionState.COLLECTING:
            return
        position = self._controller.pursuit_position(now)
        self._last_position = position
        self._position_target(position)
        snapshot = self._controller.snapshot
        self._progress.setValue(round(position.progress * 1000))
        self._progress.setFormat(
            f"{round(position.progress * 100)}% · {snapshot.total_samples} samples · "
            f"{snapshot.rejected_samples} rejected"
        )
        self._instruction.setText(
            f"Follow the target · sweep {position.segment_index + 1} of {position.segment_count}"
        )
        self._render_quality(
            snapshot.attention_state,
            snapshot.horizontal_correlation,
            snapshot.vertical_correlation,
        )
        if position.progress < 1.0:
            self._finish_deadline = None
            return
        self._instruction.setText("Live sweep complete · checking captured evidence")
        if self._finish_deadline is None:
            self._finish_deadline = now + _PIPELINE_DRAIN_SECONDS
            return
        if now >= self._finish_deadline:
            self._finish_deadline = None
            self._controller.finish_pursuit()

    def _render_quality(
        self,
        attention: PursuitAttentionState,
        horizontal: float | None,
        vertical: float | None,
    ) -> None:
        labels = {
            PursuitAttentionState.WAITING: "Waiting for the live camera signal",
            PursuitAttentionState.ACQUIRING: "Learning your eye movement · keep following",
            PursuitAttentionState.FOLLOWING: "Target following detected · live capture is healthy",
            PursuitAttentionState.NOT_FOLLOWING: (
                "Following signal is weak · look at the target and keep your head still"
            ),
        }
        correlation = ""
        if horizontal is not None and vertical is not None:
            correlation = f" · tracking H {abs(horizontal):.2f} / V {abs(vertical):.2f}"
        self._quality.setText(labels[attention] + correlation)
        self._quality.setProperty("attentionState", attention.value)
        self._quality.style().unpolish(self._quality)
        self._quality.style().polish(self._quality)

    @Slot(object)
    def _render_snapshot(self, payload: object) -> None:
        snapshot = calibration_snapshot(payload)
        state = snapshot.state
        complete = state is CalibrationSessionState.COMPLETE
        failed = state is CalibrationSessionState.TARGET_FAILED
        self._target.setVisible(
            (state in {CalibrationSessionState.AWAITING_TARGET, CalibrationSessionState.COLLECTING})
            or self._countdown_started_at is not None
        )
        if snapshot.target_position is not None:
            self._last_position = snapshot.target_position
            self._position_target(snapshot.target_position)
        if complete:
            self._animation_timer.stop()
            self._instruction.setText("Smooth Pursuit complete · calculating fit evidence")
            self._quality.setText("Live sweep captured · all nine screen regions covered")
            self._quality.setProperty("attentionState", PursuitAttentionState.FOLLOWING.value)
            self._progress.setValue(1000)
            self._progress.setFormat(
                f"100% · {snapshot.total_samples} live samples · 9 / 9 regions covered"
            )
            self._result_status.setText("Calculating result")
            self._result_status.setProperty("acceptanceState", "pending")
            self._result_summary.setText("The live target sweep was captured successfully.")
            self._result_metrics.setText("Quality evidence is being calculated.")
            self._result_explanation.setText(
                "MEYES will explain whether this result can be used for pointer output."
            )
        elif failed:
            self._animation_timer.stop()
            self._instruction.setText("Live sweep needs a retry")
            self._quality.setText("Target-following evidence was not strong enough")
            self._quality.setProperty("attentionState", PursuitAttentionState.NOT_FOLLOWING.value)
            self._progress.setValue(1000)
            self._progress.setFormat(
                f"100% · {snapshot.total_samples} samples · "
                f"{snapshot.completed_targets} / 9 regions"
            )
            self._result_status.setText("Following not confirmed")
            self._result_status.setProperty("acceptanceState", "failed")
            self._result_summary.setText(
                snapshot.failure_reason
                or "The live sweep did not produce enough reliable evidence."
            )
            self._result_metrics.setText(
                f"Captured samples: {snapshot.total_samples}\n"
                f"Screen regions covered: {snapshot.completed_targets} / 9\n"
                f"Rejected camera frames: {snapshot.rejected_samples}"
            )
            self._result_explanation.setText(
                "Keep your face centered, keep both eyes visible, and follow only the blue target."
            )
            self._feedback.setText("Nothing was activated or saved. Retry when ready.")
        if complete or failed:
            self._quality.style().unpolish(self._quality)
            self._quality.style().polish(self._quality)
        self._result_panel.setVisible(complete or failed)
        self._retry_button.setVisible(failed)
        self._return_button.setVisible(complete)
        self._cancel_button.setVisible(not complete)
        self._cancel_button.setEnabled(
            state not in {CalibrationSessionState.IDLE, CalibrationSessionState.CANCELLED}
        )
        if state is not self._last_state:
            transition_messages = {
                CalibrationSessionState.AWAITING_TARGET: (
                    "No buttons are required · capture begins after the countdown"
                ),
                CalibrationSessionState.COLLECTING: (
                    "Live capture active · follow the moving target continuously"
                ),
                CalibrationSessionState.TARGET_FAILED: (
                    "Nothing was activated or saved · adjust your position and retry"
                ),
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
            CalibrationCaptureStatus.FEATURE_UNAVAILABLE: (
                "Eyes not visible · keep your face centered and follow the target"
            ),
            CalibrationCaptureStatus.EYE_DISAGREEMENT: (
                "Eye signal is unstable · face the camera and keep both eyes open"
            ),
            CalibrationCaptureStatus.OUT_OF_RANGE: (
                "Face position is outside the reliable range · move toward the center"
            ),
            CalibrationCaptureStatus.ATTEMPT_LIMIT: (
                "Camera timing was not reliable enough · retry the live sweep"
            ),
        }
        message = messages.get(result.status)
        if message is not None:
            self._feedback.setText(message)

    @Slot(object)
    def _render_fit(self, payload: object) -> None:
        outcome = calibration_fit_outcome(payload)
        validation = outcome.validation
        self._result_metrics.setText(
            "No usable quality metrics were produced."
            if validation is None
            else (
                "Held-out quality evidence\n"
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
            summary = "The captured path could not produce a stable calibration mapper."
        elif acceptance is None:
            state = "Not evaluated"
            property_value = "pending"
            summary = "Calibration quality has not been evaluated."
        else:
            state = acceptance.state.value.replace("_", " ").title()
            property_value = acceptance.state.value
            summaries = {
                "accepted": ("All required regions were covered and the pointer mapper is ready."),
                "rejected": "This calibration did not pass the configured evidence limits.",
                "review_required": (
                    "A mapper was fitted, but activation is blocked until evidence-backed "
                    "acceptance limits are configured."
                ),
            }
            summary = summaries[property_value]
        self._instruction.setText(f"Smooth Pursuit complete · {state}")
        self._result_status.setText(state)
        self._result_status.setProperty("acceptanceState", property_value)
        self._result_status.style().unpolish(self._result_status)
        self._result_status.style().polish(self._result_status)
        self._result_summary.setText(summary)
        self._result_explanation.setText(
            f"{outcome.message} Return to Calibration to review details or start again."
        )
        self._feedback.setText(outcome.message)

    def _position_target(self, position: PursuitTargetPosition | None = None) -> None:
        current = position or self._last_position
        if current is None:
            return
        x = round(self.width() * current.x - _TARGET_SIZE / 2)
        y = round(self.height() * current.y - _TARGET_SIZE / 2)
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
        if event.key() == Qt.Key.Key_R and state is CalibrationSessionState.TARGET_FAILED:
            self._retry()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._animation_timer.stop()
        self._countdown_started_at = None
        self._finish_deadline = None
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
