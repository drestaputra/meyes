"""Qt Smooth Pursuit calibration orchestration and page tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton, QScrollArea
from pytestqt.qtbot import QtBot

from meyes.calibration.acceptance import (
    CalibrationAcceptancePolicy,
    CalibrationAcceptanceState,
)
from meyes.calibration.session import (
    CalibrationSession,
    CalibrationSessionState,
    SmoothPursuitTrajectory,
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


@dataclass
class FakeClock:
    value: float = 10.0

    def __call__(self) -> float:
        return self.value


def short_trajectory() -> SmoothPursuitTrajectory:
    return SmoothPursuitTrajectory(
        initial_hold_seconds=0.25,
        leg_duration_seconds=0.5,
        final_hold_seconds=0.25,
    )


def controller_with_clock(
    *,
    policy: CalibrationAcceptancePolicy | None = None,
) -> tuple[CalibrationController, FakeClock]:
    clock = FakeClock()
    controller = CalibrationController(
        CalibrationSession(samples_per_target=3, trajectory=short_trajectory()),
        acceptance_policy=policy,
        clock=clock,
    )
    return controller, clock


def feature(
    sequence: int,
    *,
    captured: float,
    horizontal: float = 0.5,
    vertical: float = 0.5,
) -> GazeFeatureObservation:
    return GazeFeatureObservation(
        sequence,
        captured,
        captured + 0.001,
        GazeFeatureStatus.READY,
        GazeFeatureVector(horizontal - 0.02, vertical - 0.02),
        GazeFeatureVector(horizontal + 0.02, vertical + 0.02),
        GazeFeatureVector(horizontal, vertical),
    )


def complete_calibration(
    controller: CalibrationController,
    clock: FakeClock,
    *,
    follows_target: bool,
) -> None:
    sequence = 1
    controller.start()
    controller.begin_target()
    start = clock.value
    duration = controller.pursuit_duration_seconds
    frame_count = int(duration * 30)
    for index in range(frame_count):
        elapsed = min((index + 1) / 30, duration)
        captured = start + elapsed
        position = controller.pursuit_position(captured)
        controller.observe_feature(
            feature(
                sequence,
                captured=captured,
                horizontal=position.x if follows_target else 0.5,
                vertical=position.y if follows_target else 0.5,
            )
        )
        sequence += 1
    clock.value = start + duration
    controller.finish_pursuit()


def test_controller_collects_only_during_live_sweep_and_publishes_results(
    qtbot: QtBot,
) -> None:
    controller, clock = controller_with_clock()
    results: list[object] = []
    controller.capture_decided.connect(results.append)

    controller.observe_feature(feature(1, captured=10.0))
    controller.start()
    controller.begin_target()
    for sequence in range(1, 4):
        controller.observe_feature(feature(sequence, captured=clock.value + sequence / 100))

    assert len(results) == 3
    assert controller.snapshot.state is CalibrationSessionState.COLLECTING
    assert controller.snapshot.accepted_for_target == 3
    assert controller.snapshot.total_samples == 3


def test_page_requires_tracking_and_has_no_manual_capture_or_advance_controls(
    qtbot: QtBot,
) -> None:
    controller, clock = controller_with_clock()
    prepare_calls: list[bool] = []

    def prepare() -> bool:
        prepare_calls.append(True)
        return True

    page = CalibrationPage(controller, prepare_calibration=prepare)
    qtbot.addWidget(page)
    start = page.findChild(QPushButton, "primaryButton")
    progress = page.findChild(QProgressBar, "calibrationSampleProgress")
    assert start is not None and progress is not None
    assert page.findChild(QPushButton, "captureCalibrationPointButton") is None
    assert page.findChild(QPushButton, "advanceCalibrationPointButton") is None
    assert not start.isEnabled()

    page.set_tracking_available(True)
    start.click()
    assert prepare_calls == [True]
    assert controller.snapshot.state is CalibrationSessionState.AWAITING_TARGET
    controller.begin_target()
    position = controller.pursuit_position(clock.value + 0.1)
    controller.observe_feature(
        feature(1, captured=clock.value + 0.1, horizontal=position.x, vertical=position.y)
    )

    assert controller.snapshot.state.value == CalibrationSessionState.COLLECTING.value
    assert page._progress_label.text() == "Live capture in progress"
    assert "live samples" in progress.format()


def test_saved_calibration_replace_requires_pending_state_and_modal_confirmation(
    qtbot: QtBot,
) -> None:
    controller, _clock = controller_with_clock()
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
    controller, _clock = controller_with_clock()
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
    assert "Smooth Pursuit started" in page._feedback.text()


def test_release_failure_escape_and_tracking_loss_discard_samples(qtbot: QtBot) -> None:
    controller, clock = controller_with_clock()
    page = CalibrationPage(controller, prepare_calibration=lambda: False)
    qtbot.addWidget(page)
    page.set_tracking_available(True)
    start = page.findChild(QPushButton, "primaryButton")
    feedback = page._feedback
    assert start is not None
    start.click()
    assert controller.snapshot.state is CalibrationSessionState.IDLE
    assert "could not be released" in feedback.text()

    page._prepare_calibration = lambda: True
    start.click()
    controller.begin_target()
    controller.observe_feature(feature(1, captured=clock.value + 0.1))
    qtbot.keyClick(page, Qt.Key.Key_Escape)  # type: ignore[no-untyped-call]
    assert controller.snapshot.state.value == CalibrationSessionState.CANCELLED.value
    assert controller.snapshot.total_samples == 0

    start.click()
    controller.begin_target()
    controller.observe_feature(feature(2, captured=clock.value + 0.2))
    page.set_tracking_available(False)
    assert controller.snapshot.state.value == CalibrationSessionState.CANCELLED.value
    assert controller.snapshot.total_samples == 0
    assert "tracking became unavailable" in feedback.text()


def test_arming_live_input_cancels_and_erases_live_collection(qtbot: QtBot) -> None:
    controller, clock = controller_with_clock()
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)
    page.set_tracking_available(True)
    page._start_button.click()
    controller.begin_target()
    controller.observe_feature(feature(1, captured=clock.value + 0.1))

    page.set_live_input_armed(True)

    assert controller.snapshot.state is CalibrationSessionState.CANCELLED
    assert controller.snapshot.total_samples == 0
    assert "Live Input was armed" in page._feedback.text()


def test_leaving_page_cancels_and_erases_live_collection(qtbot: QtBot) -> None:
    controller, clock = controller_with_clock()
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)
    page.set_tracking_available(True)
    page._start_button.click()
    controller.begin_target()
    controller.observe_feature(feature(1, captured=clock.value + 0.1))

    page.set_page_active(False)

    assert controller.snapshot.state is CalibrationSessionState.CANCELLED
    assert controller.snapshot.total_samples == 0
    assert "Calibration was closed" in page._feedback.text()


def test_page_region_map_is_readable_without_horizontal_overflow(qtbot: QtBot) -> None:
    controller, _clock = controller_with_clock()
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)
    page.resize(900, 640)
    page.show()

    targets = page.findChildren(QLabel, "calibrationTarget")
    assert len(targets) == 9
    assert page.minimumSizeHint().width() <= page.width()
    assert all(target.text() for target in targets)


def test_minimum_size_uses_vertical_scroll_instead_of_compressing_controls(qtbot: QtBot) -> None:
    controller, _clock = controller_with_clock()
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


def test_page_explains_rejected_live_eye_signal(qtbot: QtBot) -> None:
    controller, clock = controller_with_clock()
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)
    page.set_tracking_available(True)
    page._start_button.click()
    controller.begin_target()
    unstable = replace(
        feature(1, captured=clock.value + 0.1),
        left_eye=GazeFeatureVector(0.20, 0.20),
        right_eye=GazeFeatureVector(0.80, 0.80),
    )
    controller.observe_feature(unstable)

    assert controller.snapshot.total_samples == 0
    assert controller.snapshot.rejected_samples == 1
    assert "eye disagreement" in page._feedback.text()


def test_complete_live_sweep_fits_mapper_and_shows_holdout_metrics(qtbot: QtBot) -> None:
    controller, clock = controller_with_clock()
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)

    complete_calibration(controller, clock, follows_target=True)

    outcome = controller.fit_outcome
    assert controller.snapshot.state is CalibrationSessionState.COMPLETE
    assert controller.fit_result is not None
    assert outcome.state is CalibrationFitState.READY
    assert outcome.validation is not None
    assert outcome.validation.root_mean_square_error < 1e-10
    assert page._fit_status.text() == "Ready"
    assert page._progress_label.text() == "All 9 screen regions covered"
    assert page._progress.value() == 1000
    assert "100%" in page._progress.format()
    assert "9 / 9 regions" in page._progress.format()
    assert "RMSE 0.0000" in page._fit_metrics.text()
    assert "n=18" in page._fit_metrics.text()
    assert page._acceptance_status.text() == "Accepted"
    assert outcome.acceptance is not None
    assert outcome.acceptance.state is CalibrationAcceptanceState.ACCEPTED
    assert controller.accepted_fit_result is controller.fit_result
    assert controller.accepted_calibration is not None
    assert "Confirm Live Input" in page._feedback.text()


def test_nonfollowing_sweep_fails_before_mapper_fit(qtbot: QtBot) -> None:
    controller, clock = controller_with_clock()
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)

    complete_calibration(controller, clock, follows_target=False)

    assert controller.snapshot.state is CalibrationSessionState.TARGET_FAILED
    assert controller.fit_result is None
    assert controller.fit_outcome.state is CalibrationFitState.NONE
    assert page._fit_status.text() == "None"
    assert page._fit_metrics.text() == "—"
    assert "did not follow" in page._instruction.text()


def test_new_session_and_cancellation_erase_volatile_fit(qtbot: QtBot) -> None:
    controller, clock = controller_with_clock()
    fit_events: list[object] = []
    controller.fit_changed.connect(fit_events.append)
    complete_calibration(controller, clock, follows_target=True)
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
    controller, clock = controller_with_clock(policy=policy)
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)

    complete_calibration(controller, clock, follows_target=True)

    outcome = controller.fit_outcome
    assert outcome.acceptance is not None
    assert outcome.acceptance.state is CalibrationAcceptanceState.ACCEPTED
    assert controller.accepted_fit_result is controller.fit_result
    assert controller.accepted_calibration is not None
    assert controller.accepted_calibration.fit_result is controller.fit_result
    assert page._acceptance_status.text() == "Accepted"
    assert "produced a valid mapper" in page._feedback.text()


def test_configured_policy_rejection_never_exposes_an_accepted_fit(qtbot: QtBot) -> None:
    policy = CalibrationAcceptancePolicy(0.01, 0.01, 0.01, 19)
    controller, clock = controller_with_clock(policy=policy)
    page = CalibrationPage(controller, prepare_calibration=lambda: True)
    qtbot.addWidget(page)

    complete_calibration(controller, clock, follows_target=True)

    outcome = controller.fit_outcome
    assert outcome.acceptance is not None
    assert outcome.acceptance.state is CalibrationAcceptanceState.REJECTED
    assert controller.fit_result is not None
    assert controller.accepted_fit_result is None
    assert controller.accepted_calibration is None
    assert page._acceptance_status.text() == "Rejected"
    assert "holdout n=18 is below 19" in page._feedback.text()
    assert "Retry collection" in page._feedback.text()
