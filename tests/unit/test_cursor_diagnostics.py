"""Qt-owned cursor-candidate diagnostics tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from meyes.calibration.acceptance import (
    AcceptedCalibration,
    CalibrationAcceptance,
    CalibrationAcceptanceState,
)
from meyes.calibration.mapper import (
    CalibrationFitResult,
    CalibrationValidation,
    PolynomialCalibrationMapper,
)
from meyes.camera.buffer import LatestFrameBuffer
from meyes.config.models import GestureSettings
from meyes.cursor.pipeline import CursorPipeline
from meyes.cursor.screen_mapping import PhysicalScreenGeometry, PrimaryScreenMapper
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import (
    GazeFeatureObservation,
    GazeFeatureStatus,
    GazeFeatureVector,
)
from meyes.ui.cursor_diagnostics import CursorDiagnosticsController, CursorDiagnosticsStatus
from meyes.ui.diagnostics_page import DiagnosticsPage
from meyes.vision.controller import VisionController


@dataclass
class Clock:
    value: float = 1.0

    def __call__(self) -> float:
        return self.value


def unused_backend() -> NoReturn:
    raise RuntimeError("Backend is not started in this UI test")


def pipeline() -> CursorPipeline:
    mapper = PolynomialCalibrationMapper(
        (0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    )
    fit = CalibrationFitResult(mapper, CalibrationValidation(18, 0.01, 0.01, 0.02))
    accepted = AcceptedCalibration(
        fit,
        CalibrationAcceptance(CalibrationAcceptanceState.ACCEPTED),
    )
    return CursorPipeline(
        accepted,
        PrimaryScreenMapper(PhysicalScreenGeometry(0, 0, 1920, 1080)),
    )


def observation(sequence: int, capture: float, x: float = 0.5, y: float = 0.5) -> object:
    vector = GazeFeatureVector(x, y)
    return GazeFeatureObservation(
        sequence,
        capture,
        capture + 0.001,
        GazeFeatureStatus.READY,
        vector,
        vector,
        vector,
    )


def test_unconfigured_controller_truthfully_remains_unavailable(qtbot: QtBot) -> None:
    controller = CursorDiagnosticsController()

    controller.start()

    assert controller.snapshot.status is CursorDiagnosticsStatus.UNAVAILABLE
    assert "No accepted calibration" in controller.snapshot.message
    controller.close()


def test_ready_candidate_uses_delivery_clock_separate_from_capture_time(qtbot: QtBot) -> None:
    clock = Clock(10.0)
    controller = CursorDiagnosticsController(pipeline(), clock=clock)
    candidates: list[tuple[int, int]] = []
    controller.pointer_candidate.connect(lambda x, y: candidates.append((x, y)))
    controller.start()
    clock.value = 10.12
    controller.poll()

    controller.observe_feature(observation(1, 9.5))

    assert controller.snapshot.status is CursorDiagnosticsStatus.READY
    assert controller.snapshot.pixel_x == 960
    assert controller.snapshot.pixel_y == 540
    assert "armed Live Input" in controller.snapshot.message
    assert candidates == [(960, 540)]


def test_freshness_expiry_removes_candidate_and_suspends_pipeline(qtbot: QtBot) -> None:
    clock = Clock(1.0)
    controller = CursorDiagnosticsController(pipeline(), clock=clock, freshness_timeout=0.25)
    controller.start()
    clock.value = 1.12
    controller.poll()
    controller.observe_feature(observation(1, 0.9))
    ready_snapshot = controller.snapshot
    assert ready_snapshot.status is CursorDiagnosticsStatus.READY

    clock.value = 1.371
    controller.poll()

    stale_snapshot = controller.snapshot
    assert stale_snapshot.status is CursorDiagnosticsStatus.STALE
    assert stale_snapshot.pixel_x is None
    assert stale_snapshot.pixel_y is None


def test_temple_event_blocks_and_fresh_sample_resumes_after_delay(qtbot: QtBot) -> None:
    clock = Clock(1.0)
    controller = CursorDiagnosticsController(pipeline(), clock=clock)
    controller.start()
    clock.value = 1.12
    controller.poll()
    controller.observe_feature(observation(1, 0.9))

    clock.value = 1.13
    controller.handle_event(GestureEvent(GestureEventType.LEFT_TEMPLE_HOLD_START, 0.5, 1, 550.0))
    blocked_snapshot = controller.snapshot
    assert blocked_snapshot.status is CursorDiagnosticsStatus.BLOCKED
    assert blocked_snapshot.pixel_x is None
    clock.value = 1.2
    controller.handle_event(GestureEvent(GestureEventType.LEFT_TEMPLE_HOLD_END, 0.6, 2, 620.0))
    clock.value = 1.32
    controller.poll()
    clock.value = 1.33
    controller.observe_feature(observation(2, 1.0, 0.9, 0.9))

    resumed_snapshot = controller.snapshot
    assert resumed_snapshot.status is CursorDiagnosticsStatus.READY
    assert resumed_snapshot.pixel_x == 1727
    assert resumed_snapshot.pixel_y == 971


def test_capture_order_fault_is_contained_without_candidate(qtbot: QtBot) -> None:
    clock = Clock(1.0)
    controller = CursorDiagnosticsController(pipeline(), clock=clock)
    controller.start()
    clock.value = 1.12
    controller.poll()
    controller.observe_feature(observation(1, 1.1))
    clock.value = 1.13

    controller.observe_feature(observation(2, 1.0))

    assert controller.snapshot.status is CursorDiagnosticsStatus.FAULTED
    assert controller.snapshot.pixel_x is None
    assert controller.snapshot.pixel_y is None


def test_late_feature_clear_cannot_overwrite_suspended_lifecycle(qtbot: QtBot) -> None:
    clock = Clock(1.0)
    controller = CursorDiagnosticsController(pipeline(), clock=clock)
    controller.start()
    clock.value = 1.1
    controller.suspend()

    controller.clear_feature()

    assert controller.snapshot.status is CursorDiagnosticsStatus.SUSPENDED
    assert controller.snapshot.message == "Tracking is suspended."


def test_diagnostics_page_renders_cursor_candidate_without_executor(qtbot: QtBot) -> None:
    clock = Clock(1.0)
    cursor = CursorDiagnosticsController(pipeline(), clock=clock)
    vision = VisionController(LatestFrameBuffer(), unused_backend, GestureSettings())
    page = DiagnosticsPage(vision, cursor_diagnostics=cursor)
    qtbot.addWidget(page)
    status = page.findChild(QLabel, "cursorDiagnosticsStatus")
    gate = page.findChild(QLabel, "cursorDiagnosticsGate")
    normalized = page.findChild(QLabel, "cursorDiagnosticsNormalized")
    pixel = page.findChild(QLabel, "cursorDiagnosticsPixel")
    clamp = page.findChild(QLabel, "cursorDiagnosticsClamp")
    assert all(value is not None for value in (status, gate, normalized, pixel, clamp))

    cursor.start()
    clock.value = 1.12
    cursor.poll()
    cursor.observe_feature(observation(1, 0.9, 0.5, 0.5))

    assert status is not None and status.text() == "Ready"
    assert gate is not None and gate.text() == "Open"
    assert normalized is not None and normalized.text() == "0.5000, 0.5000"
    assert pixel is not None and pixel.text() == "960, 540"
    assert clamp is not None and clamp.text() == "No"
    assert "armed Live Input" in status.toolTip()
