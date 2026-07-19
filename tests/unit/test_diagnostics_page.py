"""Safe-mode diagnostics UI tests."""

from __future__ import annotations

from typing import NoReturn

from PySide6.QtWidgets import QLabel, QListWidget, QProgressBar
from pytestqt.qtbot import QtBot

from meyes.camera.buffer import LatestFrameBuffer
from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import (
    DetectedHand,
    FaceObservation,
    HandObservation,
    HandSide,
    TempleFeatureObservation,
    TempleFeatureStatus,
    TempleProximity,
)
from meyes.gestures.temple_proximity import ProximityState, TempleProximitySnapshot
from meyes.ui.diagnostics_page import DiagnosticsPage
from meyes.vision.controller import VisionController


def unused_backend() -> NoReturn:
    raise RuntimeError("Backend is not started in this UI test")


def test_diagnostics_renders_face_hand_temple_and_wink_signals(qtbot: QtBot) -> None:
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
    hands = HandObservation(
        source_sequence=7,
        capture_timestamp=2.0,
        processed_timestamp=2.02,
        hands=(
            DetectedHand(HandSide.LEFT, 0.9, ()),
            DetectedHand(HandSide.RIGHT, 0.9, ()),
        ),
    )
    temple = TempleFeatureObservation(
        source_sequence=7,
        capture_timestamp=2.0,
        processed_timestamp=2.02,
        status=TempleFeatureStatus.READY,
        face_source_sequence=7,
        proximities=(TempleProximity(HandSide.LEFT, 0.125, 0.9),),
    )
    proximity = TempleProximitySnapshot(
        source_sequence=7,
        timestamp=2.02,
        left=ProximityState.NEAR,
        right=ProximityState.FAR,
    )

    controller.observation_changed.emit(observation)
    controller.hand_observation_changed.emit(hands)
    controller.temple_feature_changed.emit(temple)
    controller.temple_proximity_changed.emit(proximity)

    meters = page.findChildren(QProgressBar)
    event_log = page.findChild(QListWidget, "eventLog")
    hand_count = page.findChild(QLabel, "handCountValue")
    left_temple = page.findChild(QLabel, "leftTempleValue")
    right_temple = page.findChild(QLabel, "rightTempleValue")
    left_state = page.findChild(QLabel, "leftTempleStateValue")
    right_state = page.findChild(QLabel, "rightTempleStateValue")
    assert [meter.value() for meter in meters] == [25, 85]
    assert hand_count is not None and hand_count.text() == "2"
    assert left_temple is not None and left_temple.text() == "0.125"
    assert right_temple is not None and right_temple.text() == "—"
    assert left_state is not None and left_state.text() == "Near"
    assert right_state is not None and right_state.text() == "Far"
    assert event_log is not None and event_log.count() == 0

    controller.event_detected.emit(event)

    assert event_log.count() == 1
    assert "LEFT_WINK" in event_log.item(0).text()

    controller.temple_proximity_cleared.emit()

    assert left_state.text() == "Unknown"
    assert right_state.text() == "Unknown"
    assert left_temple.text() == "0.125"
    assert right_temple.text() == "—"
