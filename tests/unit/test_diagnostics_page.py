"""Safe-mode diagnostics UI tests."""

from __future__ import annotations

from typing import NoReturn

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QProgressBar, QScrollArea
from pytestqt.qtbot import QtBot

from meyes.bindings.defaults import disabled_profile
from meyes.bindings.manager import BindingManager
from meyes.camera.buffer import LatestFrameBuffer
from meyes.config.models import GestureSettings
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.domain.observations import (
    DetectedHand,
    FaceObservation,
    GazeFeatureObservation,
    GazeFeatureStatus,
    GazeFeatureVector,
    HandObservation,
    HandSide,
    TempleFeatureObservation,
    TempleFeatureStatus,
    TempleProximity,
)
from meyes.gestures.temple_proximity import ProximityState, TempleProximitySnapshot
from meyes.ui.action_simulation import ActionSimulationController
from meyes.ui.diagnostics_page import DiagnosticsPage
from meyes.ui.theme import build_stylesheet
from meyes.vision.controller import VisionController


def unused_backend() -> NoReturn:
    raise RuntimeError("Backend is not started in this UI test")


def test_diagnostics_renders_face_hand_temple_and_semantic_events(qtbot: QtBot) -> None:
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
    gaze = GazeFeatureObservation(
        source_sequence=7,
        capture_timestamp=2.0,
        processed_timestamp=2.02,
        status=GazeFeatureStatus.READY,
        left_eye=GazeFeatureVector(0.45, 0.55),
        right_eye=GazeFeatureVector(0.55, 0.65),
        combined=GazeFeatureVector(0.50, 0.60),
    )
    wink_event = GestureEvent(
        type=GestureEventType.LEFT_WINK,
        timestamp=2.2,
        source_sequence=7,
        duration_ms=160,
    )
    temple_event = GestureEvent(
        type=GestureEventType.RIGHT_TEMPLE_HOLD_START,
        timestamp=2.8,
        source_sequence=9,
        duration_ms=550,
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
    controller.gaze_feature_changed.emit(gaze)
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
    gaze_status = page.findChild(QLabel, "gazeFeatureStatusValue")
    gaze_horizontal = page.findChild(QLabel, "gazeHorizontalValue")
    gaze_vertical = page.findChild(QLabel, "gazeVerticalValue")
    assert [meter.value() for meter in meters] == [25, 85]
    assert hand_count is not None and hand_count.text() == "2"
    assert left_temple is not None and left_temple.text() == "0.125"
    assert right_temple is not None and right_temple.text() == "—"
    assert left_state is not None and left_state.text() == "Near"
    assert right_state is not None and right_state.text() == "Far"
    assert gaze_status is not None and gaze_status.text() == "Ready"
    assert gaze_horizontal is not None and gaze_horizontal.text() == "0.500"
    assert gaze_vertical is not None and gaze_vertical.text() == "0.600"
    assert event_log is not None and event_log.count() == 0

    controller.event_detected.emit(wink_event)
    controller.event_detected.emit(temple_event)

    assert event_log.count() == 2
    assert "RIGHT HOLD START" in event_log.item(0).text()
    assert "RIGHT_TEMPLE_HOLD_START" in event_log.item(0).toolTip()
    assert "LEFT WINK" in event_log.item(1).text()

    controller.temple_proximity_cleared.emit()
    controller.gaze_feature_cleared.emit()

    assert left_state.text() == "Unknown"
    assert right_state.text() == "Unknown"
    assert left_temple.text() == "0.125"
    assert right_temple.text() == "—"
    assert gaze_status.text() == "Unavailable"
    assert gaze_horizontal.text() == "—"
    assert gaze_vertical.text() == "—"


def test_diagnostics_renders_fake_only_dispatch_state_and_result(qtbot: QtBot) -> None:
    controller = VisionController(LatestFrameBuffer(), unused_backend, GestureSettings())
    simulation = ActionSimulationController(BindingManager(), clock=lambda: 2.5)
    controller.event_detected.connect(simulation.handle_event)
    page = DiagnosticsPage(controller, action_simulation=simulation)
    qtbot.addWidget(page)
    simulation.start()

    controller.event_detected.emit(
        GestureEvent(
            type=GestureEventType.LEFT_WINK,
            timestamp=2.0,
            source_sequence=1,
            duration_ms=160.0,
        )
    )

    state = page.findChild(QLabel, "dispatchStateValue")
    profile = page.findChild(QLabel, "dispatchProfileValue")
    last_result = page.findChild(QLabel, "dispatchLastResultValue")
    fault = page.findChild(QLabel, "dispatchFaultValue")
    simulation_log = page.findChild(QListWidget, "simulatedActionLog")
    safe_banner = page.findChild(QLabel, "safeBanner")

    assert state is not None and state.text() == "Active"
    assert profile is not None and profile.text() == "Default"
    assert last_result is not None and last_result.text() == "Mouse Click · Executed"
    assert fault is not None and fault.text() == "None"
    assert simulation_log is not None and simulation_log.count() == 2
    assert "Mouse Click · left" in simulation_log.item(0).text()
    assert simulation_log.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert safe_banner is not None
    assert "Fake actions are always shown" in safe_banner.text()
    assert "Live Input state" in safe_banner.text()


def test_diagnostics_reflows_action_panel_below_observations_when_narrow(
    qtbot: QtBot,
) -> None:
    controller = VisionController(LatestFrameBuffer(), unused_backend, GestureSettings())
    long_profile_name = "A" * 80
    simulation = ActionSimulationController(BindingManager(disabled_profile(long_profile_name)))
    page = DiagnosticsPage(controller, action_simulation=simulation)
    page.setStyleSheet(build_stylesheet())
    qtbot.addWidget(page)
    page.setFixedSize(690, 640)
    page.show()

    qtbot.waitUntil(lambda: page.width() == 690 and page._compact_panels is True)
    compact_position = page._panel_grid.getItemPosition(page._panel_grid.indexOf(page._event_panel))
    panel_scroll = page.findChild(QScrollArea, "diagnosticsPanelScroll")
    safe_banner = page.findChild(QLabel, "safeBanner")
    profile_value = page.findChild(QLabel, "dispatchProfileValue")

    assert compact_position == (1, 0, 1, 2)
    assert panel_scroll is not None
    assert safe_banner is not None
    assert profile_value is not None
    assert len(profile_value.text()) <= 23
    assert "…" in profile_value.text()
    assert profile_value.toolTip() == long_profile_name
    assert page.minimumSizeHint().width() <= page.width()
    assert safe_banner.minimumSizeHint().width() <= safe_banner.width()
    assert panel_scroll.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    qtbot.waitUntil(lambda: panel_scroll.horizontalScrollBar().maximum() == 0)
    container = panel_scroll.widget()
    assert container is not None
    assert container.width() <= panel_scroll.viewport().width()
    assert all(
        panel.geometry().right() <= container.contentsRect().right()
        for panel in (page._face_panel, page._hand_panel, page._event_panel)
    )
    assert panel_scroll.verticalScrollBar().maximum() > 0

    page.setFixedSize(1190, 640)
    qtbot.waitUntil(lambda: page.width() == 1190 and page._compact_panels is False)

    wide_position = page._panel_grid.getItemPosition(page._panel_grid.indexOf(page._event_panel))
    assert wide_position == (0, 2, 1, 1)
    qtbot.waitUntil(lambda: panel_scroll.horizontalScrollBar().maximum() == 0)
    panels = (page._face_panel, page._hand_panel, page._event_panel)
    assert {panel.y() for panel in panels} == {0}
    assert [panel.x() for panel in panels] == sorted(panel.x() for panel in panels)
    assert max(panel.width() for panel in panels) - min(panel.width() for panel in panels) <= 1
    assert all(panel.geometry().right() <= container.contentsRect().right() for panel in panels)
