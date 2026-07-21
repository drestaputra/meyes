"""Safe in-shell nine-point calibration collection UI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from meyes.calibration.persistence import DeletedCalibrationBackup, DeletedCalibrationCatalog
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
from meyes.ui.calibration_persistence import CalibrationPersistenceResult
from meyes.ui.calibration_presentation import CalibrationPresentation

PrepareCalibration = Callable[[], bool]
ForgetCalibration = Callable[[], CalibrationPersistenceResult]
BackupCatalog = Callable[[], DeletedCalibrationCatalog]
RestoreCalibration = Callable[[DeletedCalibrationBackup], CalibrationPersistenceResult]
FORGET_CALIBRATION_PHRASE = "FORGET SAVED CALIBRATION"
RESTORE_CALIBRATION_PHRASE = "RESTORE SAVED CALIBRATION"


class CalibrationPage(QWidget):
    """Guide explicit volatile sampling while real OS output is disconnected."""

    def __init__(
        self,
        controller: CalibrationController,
        *,
        prepare_calibration: PrepareCalibration,
        forget_calibration: ForgetCalibration | None = None,
        backup_catalog: BackupCatalog | None = None,
        restore_calibration: RestoreCalibration | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(controller, CalibrationController):
            raise TypeError("Expected CalibrationController")
        if not callable(prepare_calibration):
            raise TypeError("prepare_calibration must be callable")
        if forget_calibration is not None and not callable(forget_calibration):
            raise TypeError("forget_calibration must be callable or None")
        if (backup_catalog is None) != (restore_calibration is None):
            raise ValueError("Backup catalog and restore callback must be configured together")
        if backup_catalog is not None and not callable(backup_catalog):
            raise TypeError("backup_catalog must be callable or None")
        if restore_calibration is not None and not callable(restore_calibration):
            raise TypeError("restore_calibration must be callable or None")
        self._controller = controller
        self._prepare_calibration = prepare_calibration
        self._forget_calibration = forget_calibration
        self._backup_catalog = backup_catalog
        self._restore_calibration = restore_calibration
        self._newest_backup: DeletedCalibrationBackup | None = None
        self._tracking_available = False
        self._presentation = CalibrationPresentation(controller, parent=self)
        self._build_ui()
        controller.snapshot_changed.connect(self._render_snapshot)
        controller.capture_decided.connect(self._show_capture_result)
        controller.fit_changed.connect(self._render_fit_outcome)
        self._render_snapshot(controller.snapshot)
        self._render_fit_outcome(controller.fit_outcome)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea(self)
        scroll.setObjectName("calibrationScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("calibrationScrollContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        title = QLabel("Calibration")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Collect volatile gaze samples at nine points and inspect held-out fit metrics. "
            "Only a mapper accepted by every configured limit is stored locally; pointer output "
            "remains disconnected."
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
        self._start_button = QPushButton("Start full-screen collection")
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
        fit_form = QFormLayout()
        self._fit_status = QLabel("Not fitted")
        self._fit_status.setObjectName("calibrationFitStatus")
        self._fit_metrics = QLabel("—")
        self._fit_metrics.setObjectName("calibrationFitMetrics")
        self._fit_metrics.setWordWrap(True)
        self._acceptance_status = QLabel("Not evaluated")
        self._acceptance_status.setObjectName("calibrationAcceptanceStatus")
        self._acceptance_status.setWordWrap(True)
        self._persistence_status = QLabel("Not loaded")
        self._persistence_status.setObjectName("calibrationPersistenceStatus")
        self._persistence_status.setWordWrap(True)
        fit_form.addRow("Volatile mapper", self._fit_status)
        fit_form.addRow("Holdout metrics", self._fit_metrics)
        fit_form.addRow("Acceptance", self._acceptance_status)
        fit_form.addRow("Saved calibration", self._persistence_status)
        panel_layout.addLayout(fit_form)
        forget_actions = QHBoxLayout()
        self._forget_confirmation = QLineEdit()
        self._forget_confirmation.setObjectName("forgetCalibrationConfirmation")
        self._forget_confirmation.setPlaceholderText(f"Type {FORGET_CALIBRATION_PHRASE}")
        self._forget_confirmation.setAccessibleName("Forget saved calibration confirmation")
        self._forget_button = QPushButton("Forget saved calibration")
        self._forget_button.setObjectName("forgetCalibrationButton")
        self._forget_button.setEnabled(False)
        forget_actions.addWidget(self._forget_confirmation, stretch=1)
        forget_actions.addWidget(self._forget_button)
        panel_layout.addLayout(forget_actions)
        self._backup_status = QLabel("Deleted backup restore is unavailable.")
        self._backup_status.setObjectName("calibrationDeletedBackupStatus")
        self._backup_status.setWordWrap(True)
        panel_layout.addWidget(self._backup_status)
        restore_actions = QHBoxLayout()
        self._restore_confirmation = QLineEdit()
        self._restore_confirmation.setObjectName("restoreCalibrationConfirmation")
        self._restore_confirmation.setPlaceholderText(f"Type {RESTORE_CALIBRATION_PHRASE}")
        self._restore_confirmation.setAccessibleName("Restore saved calibration confirmation")
        self._restore_button = QPushButton("Restore newest deleted backup")
        self._restore_button.setObjectName("restoreCalibrationButton")
        self._restore_button.setEnabled(False)
        restore_actions.addWidget(self._restore_confirmation, stretch=1)
        restore_actions.addWidget(self._restore_button)
        panel_layout.addLayout(restore_actions)
        panel_layout.addLayout(actions)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(banner)
        layout.addWidget(self._feedback)
        layout.addWidget(panel)
        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._start_button.clicked.connect(self._start)
        self._capture_button.clicked.connect(self._controller.begin_target)
        self._advance_button.clicked.connect(self._advance_or_retry)
        self._cancel_button.clicked.connect(self._controller.cancel)
        self._forget_confirmation.textChanged.connect(self._update_forget_button)
        self._forget_button.clicked.connect(self._forget_saved_calibration)
        self._restore_confirmation.textChanged.connect(self._update_restore_button)
        self._restore_button.clicked.connect(self._restore_saved_calibration)
        self._refresh_backup_catalog()

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

    def set_persistence_status(self, message: str) -> None:
        """Display one sanitized persistence lifecycle outcome."""
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Persistence status must be a non-empty string")
        self._persistence_status.setText(message.strip())

    @Slot(str)
    def _update_forget_button(self, value: str) -> None:
        self._forget_button.setEnabled(
            self._forget_calibration is not None and value == FORGET_CALIBRATION_PHRASE
        )

    @Slot()
    def _forget_saved_calibration(self) -> None:
        if (
            self._forget_calibration is None
            or self._forget_confirmation.text() != FORGET_CALIBRATION_PHRASE
        ):
            return
        try:
            result = self._forget_calibration()
        except Exception:
            self.set_persistence_status("Saved calibration could not be forgotten safely.")
        else:
            self.set_persistence_status(result.message)
        self._forget_confirmation.clear()
        self._refresh_backup_catalog()

    @Slot(str)
    def _update_restore_button(self, value: str) -> None:
        self._restore_button.setEnabled(
            self._restore_calibration is not None
            and self._newest_backup is not None
            and value == RESTORE_CALIBRATION_PHRASE
        )

    @Slot()
    def _restore_saved_calibration(self) -> None:
        backup = self._newest_backup
        if (
            self._restore_calibration is None
            or backup is None
            or self._restore_confirmation.text() != RESTORE_CALIBRATION_PHRASE
        ):
            return
        try:
            result = self._restore_calibration(backup)
        except Exception:
            self.set_persistence_status("Deleted calibration could not be restored safely.")
        else:
            self.set_persistence_status(result.message)
        self._restore_confirmation.clear()
        self._refresh_backup_catalog()

    def _refresh_backup_catalog(self) -> None:
        if self._backup_catalog is None:
            self._newest_backup = None
            self._backup_status.setText("Deleted backup restore is unavailable.")
            self._update_restore_button(self._restore_confirmation.text())
            return
        try:
            catalog = self._backup_catalog()
        except Exception:
            catalog = DeletedCalibrationCatalog((), "Deleted backup metadata is unavailable.")
        self._newest_backup = catalog.backups[0] if catalog.backups else None
        if self._newest_backup is None:
            message = catalog.warning or "No deleted calibration backup is available."
        else:
            deleted = self._newest_backup.deleted_at_utc.strftime("%Y-%m-%d %H:%M UTC")
            message = f"Newest deleted backup: {deleted} | {self._newest_backup.size_bytes} bytes."
            if catalog.warning:
                message = f"{message} Some older metadata was omitted."
        self._backup_status.setText(message)
        self._update_restore_button(self._restore_confirmation.text())

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
        self._feedback.setText(
            "Full-screen collection started. Space captures and Escape cancels safely."
        )
        if self.isVisible():
            self._presentation.present()

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
        if snapshot.state is CalibrationSessionState.COMPLETE:
            self._progress.setMaximum(len(CALIBRATION_TARGETS))
            self._progress.setValue(snapshot.completed_targets)
            self._progress.setFormat(
                f"{snapshot.completed_targets} / {len(CALIBRATION_TARGETS)} points complete"
            )
        else:
            self._progress.setMaximum(snapshot.samples_per_target)
            self._progress.setValue(snapshot.accepted_for_target)
            self._progress.setFormat(
                f"{snapshot.accepted_for_target} / {snapshot.samples_per_target} accepted"
            )
        point_number = (
            snapshot.target_index + 1 if target is not None else snapshot.completed_targets
        )
        self._progress_label.setText(
            "All 9 points complete"
            if snapshot.state is CalibrationSessionState.COMPLETE
            else f"Point {point_number} of 9"
        )
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
            CalibrationCaptureStatus.STATISTICAL_OUTLIER: (
                "Sample varied too far from this target's stable cluster; keep looking steadily."
            ),
        }
        self._feedback.setText(
            messages.get(
                result.status,
                f"Sample rejected: {result.status.value.replace('_', ' ')}.",
            )
        )

    @Slot(object)
    def _render_fit_outcome(self, payload: object) -> None:
        outcome = calibration_fit_outcome(payload)
        self._fit_status.setText(outcome.state.value.title())
        validation = outcome.validation
        self._fit_metrics.setText(
            "—"
            if validation is None
            else (
                f"RMSE {validation.root_mean_square_error:.4f} · "
                f"Mean {validation.mean_error:.4f} · Max {validation.maximum_error:.4f} · "
                f"n={validation.sample_count}"
            )
        )
        acceptance = outcome.acceptance
        self._acceptance_status.setText(
            "Not evaluated"
            if acceptance is None
            else acceptance.state.value.replace("_", " ").title()
        )
        if outcome.state is not CalibrationFitState.NONE:
            self._feedback.setText(outcome.message)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape and self._cancel_button.isEnabled():
            self._controller.cancel()
            self._feedback.setText("Collection cancelled. Volatile samples were discarded.")
            event.accept()
            return
        super().keyPressEvent(event)
