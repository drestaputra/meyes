"""Qt calibration orchestration and page tests."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QPushButton
from pytestqt.qtbot import QtBot

from meyes.calibration.session import CalibrationSession, CalibrationSessionState
from meyes.domain.observations import (
    GazeFeatureObservation,
    GazeFeatureStatus,
    GazeFeatureVector,
)
from meyes.ui.calibration_controller import CalibrationController
from meyes.ui.calibration_page import CalibrationPage


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
