"""Full-screen Smooth Pursuit presentation tests without camera or OS input."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

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
from meyes.ui.calibration_controller import CalibrationController
from meyes.ui.calibration_presentation import CalibrationPresentation


@dataclass
class FakeClock:
    value: float = 10.0

    def __call__(self) -> float:
        return self.value


def feature(
    sequence: int,
    *,
    captured: float,
    horizontal: float,
    vertical: float,
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


def setup_presentation(
    qtbot: QtBot,
) -> tuple[CalibrationController, CalibrationPresentation, FakeClock]:
    clock = FakeClock()
    trajectory = SmoothPursuitTrajectory(
        initial_hold_seconds=0.25,
        leg_duration_seconds=0.5,
        final_hold_seconds=0.25,
    )
    controller = CalibrationController(
        CalibrationSession(samples_per_target=3, trajectory=trajectory),
        clock=clock,
    )
    widget = CalibrationPresentation(controller)
    qtbot.addWidget(widget)
    widget.resize(1000, 800)
    controller.start()
    widget.show()
    return controller, widget, clock


def collect_complete_sweep(
    controller: CalibrationController,
    clock: FakeClock,
    *,
    follows_target: bool = True,
) -> None:
    controller.begin_target()
    start = clock.value
    duration = controller.pursuit_duration_seconds
    for index in range(int(duration * 30)):
        elapsed = min((index + 1) / 30, duration)
        captured = start + elapsed
        position = controller.pursuit_position(captured)
        controller.observe_feature(
            feature(
                index + 1,
                captured=captured,
                horizontal=position.x if follows_target else 0.5,
                vertical=position.y if follows_target else 0.5,
            )
        )
    clock.value = start + duration
    controller.finish_pursuit()


def test_countdown_starts_hands_free_and_target_moves_from_synchronized_clock(
    qtbot: QtBot,
) -> None:
    controller, widget, clock = setup_presentation(qtbot)
    qtbot.waitExposed(widget)
    widget._begin_countdown()

    target_center = widget._target.geometry().center()
    assert abs(target_center.x() - round(widget.width() * 0.1)) <= 1
    assert abs(target_center.y() - round(widget.height() * 0.1)) <= 1
    assert "Get ready" in widget._instruction.text()
    assert not hasattr(widget, "_capture_button")
    assert not hasattr(widget, "_next_button")

    clock.value += 3.1
    widget._animate()
    assert controller.snapshot.state.value == CalibrationSessionState.COLLECTING.value
    assert "Live capture active" in widget._feedback.text()

    clock.value += 1.0
    widget._animate()
    moved_center = widget._target.geometry().center()
    assert moved_center != target_center
    assert widget._progress.value() > 0
    assert "samples" in widget._progress.format()
    widget.close()


def test_escape_cancels_erases_and_closes_presentation(qtbot: QtBot) -> None:
    controller, widget, clock = setup_presentation(qtbot)
    controller.begin_target()
    controller.observe_feature(feature(1, captured=clock.value + 0.1, horizontal=0.1, vertical=0.1))

    qtbot.keyClick(widget, Qt.Key.Key_Escape)  # type: ignore[no-untyped-call]

    assert controller.snapshot.state is CalibrationSessionState.CANCELLED
    assert controller.snapshot.total_samples == 0
    assert not widget.isVisible()


def test_external_cancellation_closes_visible_presentation(qtbot: QtBot) -> None:
    controller, widget, _clock = setup_presentation(qtbot)

    controller.cancel()

    assert controller.snapshot.state is CalibrationSessionState.CANCELLED
    assert not widget.isVisible()


def test_return_after_completion_preserves_volatile_fit(qtbot: QtBot) -> None:
    controller, widget, clock = setup_presentation(qtbot)
    collect_complete_sweep(controller, clock)

    assert controller.snapshot.state is CalibrationSessionState.COMPLETE
    assert widget._return_button.isVisible()
    assert not widget._target.isVisible()
    assert "100%" in widget._progress.format()
    assert "9 / 9 regions covered" in widget._progress.format()
    assert widget._result_panel.isVisible()
    assert widget._result_status.text() == "Accepted"
    assert widget._result_status.property("acceptanceState") == "accepted"
    assert "RMSE:" in widget._result_metrics.text()
    assert "Holdout samples: 18" in widget._result_metrics.text()
    assert "pointer mapper is ready" in widget._result_summary.text()
    assert "Confirm Live Input" in widget._result_explanation.text()
    assert not widget._retry_button.isVisible()
    assert not widget._cancel_button.isVisible()

    widget._return_button.click()

    assert not widget.isVisible()
    assert controller.snapshot.state is CalibrationSessionState.COMPLETE
    assert controller.fit_result is not None


def test_nonfollowing_result_is_informative_and_retry_is_hands_free(qtbot: QtBot) -> None:
    controller, widget, clock = setup_presentation(qtbot)
    collect_complete_sweep(controller, clock, follows_target=False)

    assert controller.snapshot.state is CalibrationSessionState.TARGET_FAILED
    assert widget._result_panel.isVisible()
    assert widget._retry_button.isVisible()
    assert widget._result_status.text() == "Following not confirmed"
    assert "eye movement did not follow" in widget._result_summary.text().lower()
    assert "Nothing was activated" in widget._feedback.text()

    widget._retry_button.click()
    assert "Get ready" in widget._instruction.text()
    clock.value += 3.1
    widget._animate()

    assert controller.snapshot.state.value == CalibrationSessionState.COLLECTING.value
    assert controller.snapshot.total_samples == 0
    widget.close()


def test_escape_after_completion_returns_without_discarding_fit(qtbot: QtBot) -> None:
    controller, widget, clock = setup_presentation(qtbot)
    collect_complete_sweep(controller, clock)
    fitted = controller.fit_result
    assert fitted is not None

    qtbot.keyClick(widget, Qt.Key.Key_Escape)  # type: ignore[no-untyped-call]

    assert not widget.isVisible()
    assert controller.snapshot.state is CalibrationSessionState.COMPLETE
    assert controller.fit_result is fitted


def test_window_close_during_collection_cancels_and_erases(qtbot: QtBot) -> None:
    controller, widget, clock = setup_presentation(qtbot)
    controller.begin_target()
    controller.observe_feature(feature(1, captured=clock.value + 0.1, horizontal=0.1, vertical=0.1))

    widget.close()

    assert controller.snapshot.state is CalibrationSessionState.CANCELLED
    assert controller.snapshot.total_samples == 0
