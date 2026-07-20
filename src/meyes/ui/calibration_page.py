"""Safe in-shell nine-point calibration collection UI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
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
    calibration_capture_result,
    calibration_snapshot,
)

PrepareCalibration = Callable[[], bool]


class CalibrationPage(QWidget):
    """Guide explicit volatile sampling while real OS output is disconnected."""

    def __init__(
        self,
        controller: CalibrationController,
        *,
        prepare_calibration: PrepareCalibration,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(controller, CalibrationController):
            raise TypeError("Expected CalibrationController")
        if not callable(prepare_calibration):
            raise TypeError("prepare_calibration must be callable")
        self._controller = controller
        self._prepare_calibration = prepare_calibration
        self._tracking_available = False
        self._build_ui()
        controller.snapshot_changed.connect(self._render_snapshot)
        controller.capture_decided.connect(self._show_capture_result)
        self._render_snapshot(controller.snapshot)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        title = QLabel("Calibration")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Collect volatile gaze samples at nine points. This step does not yet fit a mapping, "
            "save calibration, or move the pointer."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        banner = QLabel(
            "CALIBRATION COLLECTION · Live Input is disarmed before start · Escape cancels"
        )
        banner.setObjectName("safeBanner")
        banner.setWordWrap(True)
        self._feedback = QLabel("Start tracking from Dashboard before beginning.")
        self._feedback.setObjectName("mutedText")
        self._feedback.setWordWrap(True)

        panel = QFrame()
        panel.setObjectName("statusPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(24, 24, 24, 24)
        panel_layout.setSpacing(14)
        self._instruction = QLabel("Calibration is idle")
        self._instruction.setObjectName("panelTitle")
        self._instruction.setWordWrap(True)
        self._progress_label = QLabel("Point 0 of 9")
        self._progress_label.setObjectName("calibrationProgressLabel")
        self._progress = QProgressBar()
        self._progress.setObjectName("calibrationSampleProgress")
        self._progress.setRange(0, 12)
        self._progress.setValue(0)
        self._progress.setAccessibleName("Samples accepted for current calibration point")
        target_grid = QGridLayout()
        target_grid.setSpacing(8)
        self._target_labels: list[QLabel] = []
        for index, target in enumerate(CALIBRATION_TARGETS):
            label = QLabel(f"{index + 1}. {target.label}")
            label.setObjectName("calibrationTarget")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            label.setMinimumHeight(42)
            self._target_labels.append(label)
            target_grid.addWidget(label, index // 3, index % 3)

        actions = QHBoxLayout()
        self._start_button = QPushButton("Start collection")
        self._start_button.setObjectName("primaryButton")
        self._capture_button = QPushButton("Capture current point")
        self._capture_button.setObjectName("captureCalibrationPointButton")
        self._capture_button.setProperty("primaryAction", True)
        self._advance_button = QPushButton("Next point")
        self._advance_button.setObjectName("advanceCalibrationPointButton")
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setObjectName("cancelCalibrationButton")
        actions.addWidget(self._start_button)
        actions.addWidget(self._capture_button)
        actions.addWidget(self._advance_button)
        actions.addStretch(1)
        actions.addWidget(self._cancel_button)

        panel_layout.addWidget(self._instruction)
        panel_layout.addWidget(self._progress_label)
        panel_layout.addWidget(self._progress)
        panel_layout.addLayout(target_grid)
        panel_layout.addLayout(actions)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(banner)
        layout.addWidget(self._feedback)
        layout.addWidget(panel)
        layout.addStretch(1)

        self._start_button.clicked.connect(self._start)
        self._capture_button.clicked.connect(self._controller.begin_target)
        self._advance_button.clicked.connect(self._advance_or_retry)
        self._cancel_button.clicked.connect(self._controller.cancel)

    def set_tracking_available(self, available: bool) -> None:
        """Cancel volatile collection as soon as camera tracking becomes unavailable."""
        if not isinstance(available, bool):
            raise TypeError("available must be a bool")
        if (
            self._tracking_available
            and not available
            and self._controller.snapshot.state
            not in {
                CalibrationSessionState.IDLE,
                CalibrationSessionState.CANCELLED,
            }
        ):
            self._controller.cancel()
            self._feedback.setText("Collection cancelled because tracking became unavailable.")
        self._tracking_available = available
        self._render_snapshot(self._controller.snapshot)

    def set_live_input_armed(self, armed: bool) -> None:
        """Cancel collection if real operating-system output becomes armed."""
        if not isinstance(armed, bool):
            raise TypeError("armed must be a bool")
        if armed and self._controller.snapshot.state not in {
            CalibrationSessionState.IDLE,
            CalibrationSessionState.CANCELLED,
        }:
            self._controller.cancel()
            self._feedback.setText(
                "Collection cancelled because Live Input was armed; "
                "volatile samples were discarded."
            )

    def set_page_active(self, active: bool) -> None:
        """Discard volatile samples rather than collecting while this page is hidden."""
        if not isinstance(active, bool):
            raise TypeError("active must be a bool")
        if not active and self._controller.snapshot.state not in {
            CalibrationSessionState.IDLE,
            CalibrationSessionState.CANCELLED,
        }:
            self._controller.cancel()
            self._feedback.setText(
                "Collection cancelled because Calibration was closed; "
                "volatile samples were discarded."
            )

    @Slot()
    def _start(self) -> None:
        if not self._tracking_available:
            self._feedback.setText("Start camera tracking from Dashboard first.")
            return
        try:
            prepared = self._prepare_calibration()
        except Exception:
            prepared = False
        if prepared is not True:
            self._feedback.setText("Live Input could not be released; collection was not started.")
            return
        self._controller.start()
        self._feedback.setText("Look at the highlighted point, then choose Capture current point.")

    @Slot()
    def _advance_or_retry(self) -> None:
        state = self._controller.snapshot.state
        if state is CalibrationSessionState.TARGET_COMPLETE:
            self._controller.advance()
        elif state is CalibrationSessionState.TARGET_FAILED:
            self._controller.begin_target()

    @Slot(object)
    def _render_snapshot(self, payload: object) -> None:
        snapshot = calibration_snapshot(payload)
        target = snapshot.target
        self._progress.setMaximum(snapshot.samples_per_target)
        self._progress.setValue(snapshot.accepted_for_target)
        self._progress.setFormat(
            f"{snapshot.accepted_for_target} / {snapshot.samples_per_target} accepted"
        )
        point_number = (
            snapshot.target_index + 1 if target is not None else snapshot.completed_targets
        )
        self._progress_label.setText(f"Point {point_number} of 9")
        if target is None:
            self._instruction.setText(snapshot.state.value.replace("_", " ").title())
        else:
            self._instruction.setText(f"Look at: {target.label}")
        for index, label in enumerate(self._target_labels):
            marker = "CURRENT" if target is not None and index == snapshot.target_index else ""
            completed = index < snapshot.completed_targets
            suffix = " · Done" if completed else (f" · {marker}" if marker else "")
            label.setText(f"{index + 1}. {CALIBRATION_TARGETS[index].label}{suffix}")
        state = snapshot.state
        self._start_button.setEnabled(
            self._tracking_available
            and state
            in {
                CalibrationSessionState.IDLE,
                CalibrationSessionState.CANCELLED,
                CalibrationSessionState.COMPLETE,
            }
        )
        self._capture_button.setEnabled(
            self._tracking_available and state is CalibrationSessionState.AWAITING_TARGET
        )
        self._advance_button.setEnabled(
            self._tracking_available
            and state
            in {CalibrationSessionState.TARGET_COMPLETE, CalibrationSessionState.TARGET_FAILED}
        )
        self._advance_button.setText(
            "Retry point" if state is CalibrationSessionState.TARGET_FAILED else "Next point"
        )
        self._cancel_button.setEnabled(
            state
            not in {
                CalibrationSessionState.IDLE,
                CalibrationSessionState.CANCELLED,
                CalibrationSessionState.COMPLETE,
            }
        )

    @Slot(object)
    def _show_capture_result(self, payload: object) -> None:
        result = calibration_capture_result(payload)
        messages = {
            CalibrationCaptureStatus.ACCEPTED: "Sample accepted. Keep looking at the target.",
            CalibrationCaptureStatus.TARGET_COMPLETE: "Point complete. Continue when ready.",
            CalibrationCaptureStatus.ATTEMPT_LIMIT: "Too many rejected frames. Adjust and retry.",
        }
        self._feedback.setText(
            messages.get(
                result.status,
                f"Sample rejected: {result.status.value.replace('_', ' ')}.",
            )
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape and self._cancel_button.isEnabled():
            self._controller.cancel()
            self._feedback.setText("Collection cancelled. Volatile samples were discarded.")
            event.accept()
            return
        super().keyPressEvent(event)
