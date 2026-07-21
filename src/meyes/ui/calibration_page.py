"""Safe in-shell Smooth Pursuit calibration management UI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
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
from meyes.ui.calibration_persistence import (
    CalibrationPersistenceResult,
    CalibrationPersistenceStatus,
)
from meyes.ui.calibration_presentation import CalibrationPresentation
from meyes.ui.confirmation_dialog import confirm_action

PrepareCalibration = Callable[[], bool]
ForgetCalibration = Callable[[], CalibrationPersistenceResult]
BackupCatalog = Callable[[], DeletedCalibrationCatalog]
RestoreCalibration = Callable[[DeletedCalibrationBackup], CalibrationPersistenceResult]
ConfirmCalibrationReplace = Callable[[], CalibrationPersistenceResult]
DeleteCalibrationBackup = Callable[[DeletedCalibrationBackup], CalibrationPersistenceResult]


class CalibrationPage(QWidget):
    """Guide explicit volatile sampling while real OS output is disconnected."""

    def __init__(
        self,
        controller: CalibrationController,
        *,
        prepare_calibration: PrepareCalibration,
        confirm_calibration_replace: ConfirmCalibrationReplace | None = None,
        forget_calibration: ForgetCalibration | None = None,
        backup_catalog: BackupCatalog | None = None,
        restore_calibration: RestoreCalibration | None = None,
        delete_calibration_backup: DeleteCalibrationBackup | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(controller, CalibrationController):
            raise TypeError("Expected CalibrationController")
        if not callable(prepare_calibration):
            raise TypeError("prepare_calibration must be callable")
        if forget_calibration is not None and not callable(forget_calibration):
            raise TypeError("forget_calibration must be callable or None")
        if confirm_calibration_replace is not None and not callable(confirm_calibration_replace):
            raise TypeError("confirm_calibration_replace must be callable or None")
        if (backup_catalog is None) != (restore_calibration is None):
            raise ValueError("Backup catalog and restore callback must be configured together")
        if backup_catalog is not None and not callable(backup_catalog):
            raise TypeError("backup_catalog must be callable or None")
        if restore_calibration is not None and not callable(restore_calibration):
            raise TypeError("restore_calibration must be callable or None")
        if delete_calibration_backup is not None and not callable(delete_calibration_backup):
            raise TypeError("delete_calibration_backup must be callable or None")
        if delete_calibration_backup is not None and backup_catalog is None:
            raise ValueError("Backup deletion requires a configured backup catalog")
        self._controller = controller
        self._prepare_calibration = prepare_calibration
        self._confirm_calibration_replace = confirm_calibration_replace
        self._forget_calibration = forget_calibration
        self._backup_catalog = backup_catalog
        self._restore_calibration = restore_calibration
        self._delete_calibration_backup = delete_calibration_backup
        self._newest_backup: DeletedCalibrationBackup | None = None
        self._replace_required = False
        self._tracking_available = False
        self._presentation = CalibrationPresentation(controller, parent=self)
        self._build_ui()
        controller.snapshot_changed.connect(self._render_snapshot)
        controller.capture_decided.connect(self._show_capture_result)
        controller.fit_changed.connect(self._render_fit_outcome)
        self._render_snapshot(controller.snapshot)
        self._render_fit_outcome(controller.fit_outcome)

    @property
    def modal_parent(self) -> QWidget:
        """Keep post-calibration dialogs above the visible full-screen presentation."""
        return self._presentation if self._presentation.isVisible() else self

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea(self)
        scroll.setObjectName("calibrationScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll = scroll
        content = QWidget()
        content.setObjectName("calibrationScrollContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)
        title = QLabel("Calibration")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Follow one moving target while MEYES captures gaze continuously and verifies "
            "that eye movement follows the live path across all nine screen regions. "
            "A completed valid mapper becomes available immediately; MEYES asks before activating "
            "Live Input and disarms it before collection or replacement."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        banner = QLabel(
            "SMOOTH PURSUIT · Hands-free live capture · Live Input is disarmed · Escape cancels"
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
        self._progress_label = QLabel("Live sweep idle")
        self._progress_label.setObjectName("calibrationProgressLabel")
        self._progress = QProgressBar()
        self._progress.setObjectName("calibrationSampleProgress")
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.setAccessibleName("Smooth pursuit calibration progress")
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
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setObjectName("cancelCalibrationButton")
        actions.addWidget(self._start_button)
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
        replace_instruction = QLabel(
            "A newly accepted fit remains volatile when a saved calibration already exists. "
            "Select Replace saved calibration and confirm the modal dialog to replace it."
        )
        replace_instruction.setObjectName("mutedText")
        replace_instruction.setWordWrap(True)
        panel_layout.addWidget(replace_instruction)
        self._replace_button = QPushButton("Replace saved calibration")
        self._replace_button.setObjectName("replaceCalibrationButton")
        self._replace_button.setEnabled(False)
        panel_layout.addWidget(self._replace_button)
        self._forget_button = QPushButton("Forget saved calibration")
        self._forget_button.setObjectName("forgetCalibrationButton")
        self._forget_button.setEnabled(self._forget_calibration is not None)
        panel_layout.addWidget(self._forget_button)
        self._backup_status = QLabel("Deleted backup restore is unavailable.")
        self._backup_status.setObjectName("calibrationDeletedBackupStatus")
        self._backup_status.setWordWrap(True)
        panel_layout.addWidget(self._backup_status)
        self._restore_button = QPushButton("Restore newest deleted backup")
        self._restore_button.setObjectName("restoreCalibrationButton")
        self._restore_button.setEnabled(False)
        panel_layout.addWidget(self._restore_button)
        self._delete_backup_button = QPushButton("Permanently delete newest backup")
        self._delete_backup_button.setObjectName("deleteCalibrationBackupButton")
        self._delete_backup_button.setProperty("dangerAction", True)
        self._delete_backup_button.setEnabled(False)
        panel_layout.addWidget(self._delete_backup_button)
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
        self._cancel_button.clicked.connect(self._controller.cancel)
        self._replace_button.clicked.connect(self._replace_saved_calibration)
        self._forget_button.clicked.connect(self._forget_saved_calibration)
        self._restore_button.clicked.connect(self._restore_saved_calibration)
        self._delete_backup_button.clicked.connect(self._delete_saved_calibration_backup)
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

    def show_camera_ready_onboarding(self) -> None:
        """Enter guided calibration after an uncalibrated camera start."""

        if not self._tracking_available:
            return
        if self._controller.snapshot.state not in {
            CalibrationSessionState.IDLE,
            CalibrationSessionState.CANCELLED,
        }:
            return
        self._instruction.setText("Camera ready · starting calibration onboarding")
        self._feedback.setText("Preparing hands-free Smooth Pursuit live capture.")
        self._scroll.ensureWidgetVisible(self._start_button)
        QTimer.singleShot(0, self._start_camera_onboarding)

    @Slot()
    def _start_camera_onboarding(self) -> None:
        if self.isVisible() and self._tracking_available:
            self._start()

    def set_persistence_status(self, message: str) -> None:
        """Display one sanitized persistence lifecycle outcome."""
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Persistence status must be a non-empty string")
        self._persistence_status.setText(message.strip())

    def set_persistence_result(self, result: CalibrationPersistenceResult) -> None:
        """Render persistence status and modal-confirmation availability."""

        if not isinstance(result, CalibrationPersistenceResult):
            raise TypeError("Expected CalibrationPersistenceResult")
        self.set_persistence_status(result.message)
        self._replace_required = result.status is CalibrationPersistenceStatus.PENDING_REPLACE
        self._update_replace_button()

    def _update_replace_button(self) -> None:
        self._replace_button.setEnabled(
            self._replace_required and self._confirm_calibration_replace is not None
        )

    @Slot()
    def _replace_saved_calibration(self) -> None:
        if not self._replace_required or self._confirm_calibration_replace is None:
            return
        if not confirm_action(
            self,
            title="Replace saved calibration?",
            message=(
                "Replace the existing saved calibration with the accepted calibration active "
                "for this session? Live Input will be released before replacement."
            ),
            confirm_label="Replace calibration",
            destructive=True,
        ):
            return
        try:
            result = self._confirm_calibration_replace()
        except Exception:
            self.set_persistence_status("Saved calibration could not be replaced safely.")
        else:
            self.set_persistence_result(result)

    @Slot()
    def _forget_saved_calibration(self) -> None:
        if self._forget_calibration is None:
            return
        if not confirm_action(
            self,
            title="Forget saved calibration?",
            message=(
                "Move the saved calibration to a recoverable deleted backup and clear the "
                "active cursor calibration? Live Input will remain disconnected."
            ),
            confirm_label="Forget calibration",
            destructive=True,
        ):
            return
        try:
            result = self._forget_calibration()
        except Exception:
            self.set_persistence_status("Saved calibration could not be forgotten safely.")
        else:
            self.set_persistence_result(result)
        self._refresh_backup_catalog()

    def _update_restore_button(self) -> None:
        self._restore_button.setEnabled(
            self._restore_calibration is not None and self._newest_backup is not None
        )

    @Slot()
    def _restore_saved_calibration(self) -> None:
        backup = self._newest_backup
        if self._restore_calibration is None or backup is None:
            return
        if not confirm_action(
            self,
            title="Restore deleted calibration?",
            message=(
                "Restore the newest deleted calibration backup? It will be revalidated against "
                "the current policy and display and will not arm Live Input."
            ),
            confirm_label="Restore backup",
        ):
            return
        try:
            result = self._restore_calibration(backup)
        except Exception:
            self.set_persistence_status("Deleted calibration could not be restored safely.")
        else:
            self.set_persistence_result(result)
        self._refresh_backup_catalog()

    def _update_delete_backup_button(self) -> None:
        self._delete_backup_button.setEnabled(
            self._delete_calibration_backup is not None and self._newest_backup is not None
        )

    @Slot()
    def _delete_saved_calibration_backup(self) -> None:
        backup = self._newest_backup
        if self._delete_calibration_backup is None or backup is None:
            return
        if not confirm_action(
            self,
            title="Permanently delete calibration backup?",
            message=(
                "Permanently delete the newest calibration backup? This cannot be undone. "
                "The active calibration and Live Input state will not be changed."
            ),
            confirm_label="Delete permanently",
            destructive=True,
        ):
            return
        try:
            result = self._delete_calibration_backup(backup)
        except Exception:
            self.set_persistence_status("Calibration backup could not be removed safely.")
        else:
            self.set_persistence_result(result)
        self._refresh_backup_catalog()

    def _refresh_backup_catalog(self) -> None:
        if self._backup_catalog is None:
            self._newest_backup = None
            self._backup_status.setText("Deleted backup restore is unavailable.")
            self._update_restore_button()
            self._update_delete_backup_button()
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
        self._update_restore_button()
        self._update_delete_backup_button()

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
            "Full-screen Smooth Pursuit started. Follow the target; capture is automatic."
        )
        if self.isVisible():
            self._presentation.present()

    @Slot(object)
    def _render_snapshot(self, payload: object) -> None:
        snapshot = calibration_snapshot(payload)
        target = snapshot.target
        self._progress.setRange(0, 1000)
        self._progress.setValue(round(snapshot.progress * 1000))
        self._progress.setFormat(
            f"{round(snapshot.progress * 100)}% · {snapshot.total_samples} live samples · "
            f"{snapshot.completed_targets} / 9 regions"
        )
        state = snapshot.state
        progress_labels = {
            CalibrationSessionState.IDLE: "Live sweep idle",
            CalibrationSessionState.AWAITING_TARGET: "Hands-free countdown ready",
            CalibrationSessionState.COLLECTING: "Live capture in progress",
            CalibrationSessionState.TARGET_FAILED: "Live sweep needs a retry",
            CalibrationSessionState.COMPLETE: "All 9 screen regions covered",
            CalibrationSessionState.CANCELLED: "Live sweep cancelled",
        }
        self._progress_label.setText(
            progress_labels.get(state, state.value.replace("_", " ").title())
        )
        if state is CalibrationSessionState.COLLECTING and target is not None:
            self._instruction.setText(
                f"Follow the moving target · currently crossing {target.label.lower()}"
            )
        elif state is CalibrationSessionState.TARGET_FAILED:
            self._instruction.setText(snapshot.failure_reason or "Live following was not confirmed")
        elif state is CalibrationSessionState.COMPLETE:
            self._instruction.setText("Smooth Pursuit capture complete")
        else:
            self._instruction.setText(progress_labels.get(state, "Smooth Pursuit calibration"))
        for index, label in enumerate(self._target_labels):
            completed = CALIBRATION_TARGETS[index].name in snapshot.covered_targets
            current = target is not None and index == snapshot.target_index
            suffix = " · Covered" if completed else (" · Live" if current else "")
            label.setText(f"{index + 1}. {CALIBRATION_TARGETS[index].label}{suffix}")
        self._start_button.setEnabled(
            self._tracking_available
            and state
            in {
                CalibrationSessionState.IDLE,
                CalibrationSessionState.CANCELLED,
                CalibrationSessionState.COMPLETE,
            }
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
            CalibrationCaptureStatus.ACCEPTED: "Live sample captured. Keep following the target.",
            CalibrationCaptureStatus.ATTEMPT_LIMIT: (
                "Camera timing limit reached. Adjust and retry."
            ),
            CalibrationCaptureStatus.FEATURE_UNAVAILABLE: (
                "Both eyes must remain visible during the live sweep."
            ),
            CalibrationCaptureStatus.EYE_DISAGREEMENT: (
                "Sample rejected: eye disagreement. Face the camera and keep both eyes open."
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
