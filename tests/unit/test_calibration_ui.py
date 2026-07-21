"""Qt calibration orchestration and page tests."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QScrollArea
from pytestqt.qtbot import QtBot

from meyes.calibration.acceptance import (
    CalibrationAcceptancePolicy,
    CalibrationAcceptanceState,
)
from meyes.calibration.session import (
    CALIBRATION_TARGETS,
    CalibrationSession,
    CalibrationSessionState,
    CalibrationTarget,
)
from meyes.domain.observations import (
    GazeFeatureObservation,
    GazeFeatureStatus,
    GazeFeatureVector,
)
from meyes.ui.calibration_controller import (
    CalibrationController,
    CalibrationFitState,
    calibration_fit_outcome,
)
from meyes.ui.calibration_page import CalibrationPage
from meyes.ui.calibration_persistence import (
    CalibrationPersistenceResult,
    CalibrationPersistenceStatus,
)


def feature(sequence: int) -> GazeFeatureObservation:
    return GazeFeatureObservation(
        sequence,
        sequence / 100,
        sequence / 100 + 0.001,
        GazeFeatureStatus.READY,
        GazeFeatureVector(0.45, 0.45),
        GazeFeatureVector(0.55, 0.55),
        GazeFeatureVector(0.5, 0.5),
    )


def target_feature(sequence: int, target: CalibrationTarget) -> GazeFeatureObservation:
    return GazeFeatureObservation(
        sequence,
        sequence / 100,
        sequence / 100 + 0.001,
        GazeFeatureStatus.READY,
        GazeFeatureVector(target.x - 0.05, target.y - 0.05),
        GazeFeatureVector(target.x + 0.05, target.y + 0.05),
        GazeFeatureVector(target.x, target.y),
    )


def complete_calibration(
    controller: CalibrationController,
    *,
    stable_geometry: bool,
) -> None:
    sequence = 1
    controller.start()
    for target in CALIBRATION_TARGETS:
        controller.begin_target()
        for _sample in range(3):
            observation = target_feature(sequence, target) if stable_geometry else feature(sequence)
            controller.observe_feature(observation)
            sequence += 1
        controller.advance()


def test_controller_collects_only_while_armed_and_publishes_results(qtbot: QtBot) -> None:
    controller = CalibrationController(
        CalibrationSession(samples_per_target=3, max_attempts_per_target=6)
    )
    results: list[object] = []
    controller.capture_decided.connect(results.append)

    controller.observe_feature(feature(1))
    controller.start()
    controller.begin_target()
    for sequence in range(1, 4):
        controller.observe_feature(feature(sequence))

    assert len(results) == 3
    assert controller.snapshot.state is CalibrationSessionState.TARGET_COMPLETE
    assert controller.snapshot.accepted_for_target == 3


def test_page_requires_tracking_and_release_then_completes_target(qtbot: QtBot) -> None:
    controller = CalibrationController(
        CalibrationSession(samples_per_target=3, max_attempts_per_target=6)
    )
    prepare_calls: list[bool] = []

    def prepare() -> bool:
        prepare_calls.append(True)
        return True

    page = CalibrationPage(
        controller,
        prepare_calibration=prepare,
    )
    qtbot.addWidget(page)
    start = page.findChild(QPushButton, "primaryButton")
    capture = page.findChild(QPushButton, "captureCalibrationPointButton")
    advance = page.findChild(QPushButton, "advanceCalibrationPointButton")
    progress = page.findChild(QProgressBar, "calibrationSampleProgress")
    assert start is not None and capture is not None and advance is not None
    assert progress is not None
    assert not start.isEnabled()

    page.set_tracking_available(True)
    start.click()
    capture.click()
    for sequence in range(1, 4):
        controller.observe_feature(feature(sequence))

    assert prepare_calls == [True]
    assert controller.snapshot.state.value == CalibrationSessionState.TARGET_COMPLETE.value
    assert progress.value() == 3
    assert advance.isEnabled()
    advance.click()
    assert controller.snapshot.target_index == 1
    assert controller.snapshot.state.value == CalibrationSessionState.AWAITING_TARGET.value


def test_saved_calibration_replace_requires_pending_state_and_modal_confirmation(
    qtbot: QtBot,
) -> None:
    controller = CalibrationController()
    calls: list[bool] = []

    def confirm_replace() -> CalibrationPersistenceResult:
        calls.append(True)
        return CalibrationPersistenceResult(
            CalibrationPersistenceStatus.SAVED,
            "Saved replacement.",
        )

    page = CalibrationPage(
        controller,
        prepare_calibration=lambda: True,
        confirm_calibration_replace=confirm_replace,
    )
    qtbot.addWidget(page)
    button = page.findChild(QPushButton, "replaceCalibrationButton")
    assert button is not None
    assert not button.isEnabled()

    page.set_persistence_result(
        CalibrationPersistenceResult(
            CalibrationPersistenceStatus.PENDING_REPLACE,
            "Confirmation required.",
        )
    )
    assert button.isEnabled()

    with patch("meyes.ui.calibration_page.confirm_action", return_value=False) as confirm:
        button.click()
    assert calls == []
    confirm.assert_called_once()

    with patch("meyes.ui.calibration_page.confirm_action", return_value=True) as confirm:
        button.click()

    assert calls == [True]
    assert confirm.call_args.kwargs["destructive"] is True
    assert confirm.call_args.kwargs["confirm_label"] == "Replace calibration"
    assert page._persistence_status.text() == "Saved replacement."
    assert not button.isEnabled()


def test_visible_page_launches_full_screen_presentation(qtbot: QtBot) -> None:
    controller = CalibrationController(CalibrationSession(samples_per_target=3))
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)
    page.set_tracking_available(True)
    page.resize(900, 640)
    page.show()
    qtbot.waitExposed(page)

    with patch.object(page._presentation, "present") as present:
        page._start_button.click()

    present.assert_called_once_with()
    assert controller.snapshot.state is CalibrationSessionState.AWAITING_TARGET
    assert "Full-screen collection started" in page._feedback.text()


def test_release_failure_escape_and_tracking_loss_discard_samples(qtbot: QtBot) -> None:
    controller = CalibrationController(CalibrationSession(samples_per_target=3))
    page = CalibrationPage(controller, prepare_calibration=lambda: False)
    qtbot.addWidget(page)
    page.set_tracking_available(True)
    start = page.findChild(QPushButton, "primaryButton")
    capture = page.findChild(QPushButton, "captureCalibrationPointButton")
    feedback = page._feedback
    assert start is not None and capture is not None
    start.click()
    assert controller.snapshot.state.value == CalibrationSessionState.IDLE.value
    assert "could not be released" in feedback.text()

    page._prepare_calibration = lambda: True
    start.click()
    capture.click()
    controller.observe_feature(feature(1))
    qtbot.keyClick(page, Qt.Key.Key_Escape)  # type: ignore[no-untyped-call]
    assert controller.snapshot.state.value == CalibrationSessionState.CANCELLED.value
    assert controller.snapshot.total_samples == 0

    start.click()
    capture.click()
    controller.observe_feature(feature(2))
    page.set_tracking_available(False)
    assert controller.snapshot.state.value == CalibrationSessionState.CANCELLED.value
    assert controller.snapshot.total_samples == 0
    assert "tracking became unavailable" in feedback.text()


def test_arming_live_input_cancels_and_erases_collection(qtbot: QtBot) -> None:
    controller = CalibrationController(CalibrationSession(samples_per_target=3))
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)
    page.set_tracking_available(True)
    page._start_button.click()
    page._capture_button.click()
    controller.observe_feature(feature(1))

    page.set_live_input_armed(True)

    assert controller.snapshot.state is CalibrationSessionState.CANCELLED
    assert controller.snapshot.total_samples == 0
    assert "Live Input was armed" in page._feedback.text()


def test_leaving_page_cancels_and_erases_collection(qtbot: QtBot) -> None:
    controller = CalibrationController(CalibrationSession(samples_per_target=3))
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)
    page.set_tracking_available(True)
    page._start_button.click()
    page._capture_button.click()
    controller.observe_feature(feature(1))

    page.set_page_active(False)

    assert controller.snapshot.state is CalibrationSessionState.CANCELLED
    assert controller.snapshot.total_samples == 0
    assert "Calibration was closed" in page._feedback.text()


def test_page_target_map_is_readable_without_horizontal_overflow(qtbot: QtBot) -> None:
    controller = CalibrationController()
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)
    page.resize(900, 640)
    page.show()

    targets = page.findChildren(QLabel, "calibrationTarget")
    assert len(targets) == 9
    assert page.minimumSizeHint().width() <= page.width()
    assert all(target.text() for target in targets)


def test_minimum_size_uses_vertical_scroll_instead_of_compressing_controls(qtbot: QtBot) -> None:
    controller = CalibrationController()
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)
    page.resize(680, 536)
    page.show()
    qtbot.waitExposed(page)
    scroll = page.findChild(QScrollArea, "calibrationScrollArea")
    assert scroll is not None

    assert scroll.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.horizontalScrollBar().maximum() == 0
    assert scroll.verticalScrollBar().maximum() > 0
    assert page._fit_status.height() > 0
    assert page._forget_button.height() > 0
    assert page._restore_button.height() > 0


def test_page_explains_statistical_outlier_without_advancing_progress(qtbot: QtBot) -> None:
    controller = CalibrationController(
        CalibrationSession(samples_per_target=5, max_attempts_per_target=9)
    )
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)
    page.set_tracking_available(True)
    page._start_button.click()
    page._capture_button.click()
    for sequence in range(1, 5):
        controller.observe_feature(feature(sequence))
    outlier = replace(
        feature(5),
        left_eye=GazeFeatureVector(0.85, 0.45),
        right_eye=GazeFeatureVector(0.95, 0.55),
        combined=GazeFeatureVector(0.90, 0.50),
    )
    controller.observe_feature(outlier)

    assert controller.snapshot.accepted_for_target == 4
    assert "varied too far" in page._feedback.text()


def test_complete_collection_fits_volatile_mapper_and_shows_holdout_metrics(
    qtbot: QtBot,
) -> None:
    controller = CalibrationController(CalibrationSession(samples_per_target=3))
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)

    complete_calibration(controller, stable_geometry=True)

    outcome = controller.fit_outcome
    assert controller.snapshot.state is CalibrationSessionState.COMPLETE
    assert controller.fit_result is not None
    assert outcome.state is CalibrationFitState.READY
    assert outcome.validation is not None
    assert outcome.validation.root_mean_square_error < 1e-10
    assert page._fit_status.text() == "Ready"
    assert page._progress_label.text() == "All 9 points complete"
    assert page._progress.value() == 9
    assert page._progress.format() == "9 / 9 points complete"
    assert "RMSE 0.0000" in page._fit_metrics.text()
    assert "n=18" in page._fit_metrics.text()
    assert page._acceptance_status.text() == "Review Required"
    assert outcome.acceptance is not None
    assert outcome.acceptance.state is CalibrationAcceptanceState.REVIEW_REQUIRED
    assert controller.accepted_fit_result is None
    assert controller.accepted_calibration is None
    assert "Review is required" in page._feedback.text()


def test_unstable_complete_collection_reports_fit_failure_without_mapper(
    qtbot: QtBot,
) -> None:
    controller = CalibrationController(CalibrationSession(samples_per_target=3))
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)

    complete_calibration(controller, stable_geometry=False)

    assert controller.snapshot.state is CalibrationSessionState.COMPLETE
    assert controller.fit_result is None
    assert controller.fit_outcome.state is CalibrationFitState.FAILED
    assert controller.fit_outcome.validation is None
    assert controller.fit_outcome.acceptance is None
    assert page._fit_status.text() == "Failed"
    assert page._fit_metrics.text() == "—"
    assert "Retry collection" in page._feedback.text()


def test_new_session_and_cancellation_erase_volatile_fit(qtbot: QtBot) -> None:
    controller = CalibrationController(CalibrationSession(samples_per_target=3))
    fit_events: list[object] = []
    controller.fit_changed.connect(fit_events.append)
    complete_calibration(controller, stable_geometry=True)
    fitted_result = controller.fit_result
    assert fitted_result is not None

    controller.start()
    assert controller.fit_result is None
    assert controller.fit_outcome.state is CalibrationFitState.NONE
    assert calibration_fit_outcome(fit_events[-1]).state is CalibrationFitState.NONE

    controller.cancel()
    assert controller.fit_result is None
    assert controller.fit_outcome.state is CalibrationFitState.NONE


def test_configured_policy_exposes_only_an_accepted_fit(qtbot: QtBot) -> None:
    policy = CalibrationAcceptancePolicy(0.01, 0.01, 0.01, 18)
    controller = CalibrationController(
        CalibrationSession(samples_per_target=3),
        acceptance_policy=policy,
    )
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)

    complete_calibration(controller, stable_geometry=True)

    outcome = controller.fit_outcome
    assert outcome.acceptance is not None
    assert outcome.acceptance.state is CalibrationAcceptanceState.ACCEPTED
    assert controller.accepted_fit_result is controller.fit_result
    assert controller.accepted_calibration is not None
    assert controller.accepted_calibration.fit_result is controller.fit_result
    assert page._acceptance_status.text() == "Accepted"
    assert "meets every configured acceptance limit" in page._feedback.text()


def test_configured_policy_rejection_never_exposes_an_accepted_fit(qtbot: QtBot) -> None:
    policy = CalibrationAcceptancePolicy(0.01, 0.01, 0.01, 19)
    controller = CalibrationController(
        CalibrationSession(samples_per_target=3),
        acceptance_policy=policy,
    )
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)

    complete_calibration(controller, stable_geometry=True)

    outcome = controller.fit_outcome
    assert outcome.acceptance is not None
    assert outcome.acceptance.state is CalibrationAcceptanceState.REJECTED
    assert controller.fit_result is not None
    assert controller.accepted_fit_result is None
    assert controller.accepted_calibration is None
    assert page._acceptance_status.text() == "Rejected"
    assert "holdout n=18 is below 19" in page._feedback.text()
    assert "Retry collection" in page._feedback.text()
