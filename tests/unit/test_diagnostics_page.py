"""Safe-mode diagnostics UI tests."""

from __future__ import annotations

from typing import NoReturn

from PySide6.QtWidgets import QListWidget, QProgressBar
from pytestqt.qtbot import QtBot

from meyes.camera.buffer import LatestFrameBuffer
from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import FaceObservation
from meyes.ui.diagnostics_page import DiagnosticsPage
from meyes.vision.controller import VisionController


def unused_backend() -> NoReturn:
    raise RuntimeError("Backend is not started in this UI test")


def test_diagnostics_renders_eye_values_and_semantic_event(qtbot: QtBot) -> None:
    controller = VisionController(LatestFrameBuffer(), unused_backend, GestureSettings())
    page = DiagnosticsPage(controller)
    qtbot.addWidget(page)
    observation = FaceObservation(
        source_sequence=7,
        capture_timestamp=2.0,
        processed_timestamp=2.01,
        face_detected=True,
        left_eye_openness=0.25,
        right_eye_openness=0.85,
    )
    event = GestureEvent(
        type=GestureEventType.LEFT_WINK,
        timestamp=2.2,
        source_sequence=7,
        duration_ms=160,
    )

    controller.observation_changed.emit(observation)
    controller.event_detected.emit(event)

    meters = page.findChildren(QProgressBar)
    event_log = page.findChild(QListWidget, "eventLog")
    assert [meter.value() for meter in meters] == [25, 85]
    assert event_log is not None
    assert event_log.count() == 1
    assert "LEFT_WINK" in event_log.item(0).text()
