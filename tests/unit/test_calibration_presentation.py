"""Full-screen calibration presentation tests without camera or OS input."""

from __future__ import annotations

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

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
from meyes.ui.calibration_controller import CalibrationController
from meyes.ui.calibration_presentation import CalibrationPresentation


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


def complete_calibration(controller: CalibrationController) -> None:
    sequence = 1
    controller.start()
    for target in CALIBRATION_TARGETS:
        controller.begin_target()
        for _sample in range(3):
            controller.observe_feature(target_feature(sequence, target))
            sequence += 1
        controller.advance()


def presentation(qtbot: QtBot) -> tuple[CalibrationController, CalibrationPresentation]:
    controller = CalibrationController(CalibrationSession(samples_per_target=3))
    widget = CalibrationPresentation(controller)
    qtbot.addWidget(widget)
    widget.resize(1000, 800)
    controller.start()
    widget.show()
    return controller, widget


def test_target_uses_normalized_screen_position_and_keyboard_progression(
    qtbot: QtBot,
) -> None:
    controller, widget = presentation(qtbot)
    qtbot.waitExposed(widget)

    target_center = widget._target.geometry().center()
    assert abs(target_center.x() - 100) <= 1
    assert abs(target_center.y() - 80) <= 1
    assert widget._capture_button.isEnabled()
    assert "press Space" in widget._feedback.text()

    qtbot.keyClick(widget, Qt.Key.Key_Space)  # type: ignore[no-untyped-call]
    collecting_snapshot = controller.snapshot
    assert collecting_snapshot.state is CalibrationSessionState.COLLECTING
    first_target = collecting_snapshot.target
    assert first_target is not None
    for sequence in range(1, 4):
        controller.observe_feature(target_feature(sequence, first_target))
    completed_snapshot = controller.snapshot
    assert completed_snapshot.state is CalibrationSessionState.TARGET_COMPLETE

    qtbot.keyClick(widget, Qt.Key.Key_Return)  # type: ignore[no-untyped-call]
    awaiting_snapshot = controller.snapshot
    assert awaiting_snapshot.state is CalibrationSessionState.AWAITING_TARGET
    assert awaiting_snapshot.target_index == 1
    second_center = widget._target.geometry().center()
    assert abs(second_center.x() - 500) <= 1
    assert abs(second_center.y() - 80) <= 1


def test_escape_cancels_erases_and_closes_presentation(qtbot: QtBot) -> None:
    controller, widget = presentation(qtbot)
    qtbot.keyClick(widget, Qt.Key.Key_Space)  # type: ignore[no-untyped-call]
    controller.observe_feature(feature(1))

    qtbot.keyClick(widget, Qt.Key.Key_Escape)  # type: ignore[no-untyped-call]

    assert controller.snapshot.state is CalibrationSessionState.CANCELLED
    assert controller.snapshot.total_samples == 0
    assert not widget.isVisible()


def test_external_cancellation_closes_visible_presentation(qtbot: QtBot) -> None:
    controller, widget = presentation(qtbot)

    controller.cancel()

    assert controller.snapshot.state is CalibrationSessionState.CANCELLED
    assert not widget.isVisible()


def test_return_after_completion_preserves_volatile_fit(qtbot: QtBot) -> None:
    controller = CalibrationController(CalibrationSession(samples_per_target=3))
    widget = CalibrationPresentation(controller)
    qtbot.addWidget(widget)
    widget.resize(1000, 800)
    widget.show()
    complete_calibration(controller)

    assert controller.snapshot.state is CalibrationSessionState.COMPLETE
    assert widget._return_button.isVisible()
    assert not widget._target.isVisible()
    assert widget._progress.format() == "9 / 9 points complete"

    widget._return_button.click()

    assert not widget.isVisible()
    assert controller.snapshot.state is CalibrationSessionState.COMPLETE
    assert controller.fit_result is not None


def test_window_close_during_collection_cancels_and_erases(qtbot: QtBot) -> None:
    controller, widget = presentation(qtbot)
    widget._capture_button.click()
    controller.observe_feature(feature(1))

    widget.close()

    assert controller.snapshot.state is CalibrationSessionState.CANCELLED
    assert controller.snapshot.total_samples == 0
