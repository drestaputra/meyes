"""Live safe-mode face, hand, temple, and gesture diagnostics."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from meyes.domain.observations import HandSide
from meyes.ui.action_simulation import (
    ActionSimulationController,
    simulation_input_call,
    simulation_report,
    simulation_snapshot,
)
from meyes.vision.controller import (
    VisionController,
    face_observation,
    gaze_feature_observation,
    gesture_event,
    hand_observation,
    hand_vision_health,
    temple_feature_observation,
    temple_proximity_snapshot,
    vision_health,
)

_COMPACT_PANEL_BREAKPOINT = 960
_MAX_PROFILE_DISPLAY_CHARS = 23


class EyeMeter(QFrame):
    """Labelled openness meter with explicit unavailable state."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("meterGroup")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        name = QLabel(label)
        name.setObjectName("mutedText")
        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setValue(0)
        self.meter.setFormat("Unavailable")
        self.meter.setAccessibleName(label)
        layout.addWidget(name)
        layout.addWidget(self.meter)

    def set_openness(self, openness: float | None) -> None:
        """Render a normalized score or explicit unavailable state."""
        if openness is None:
            self.meter.setValue(0)
            self.meter.setFormat("Unavailable")
            return
        percent = round(max(0.0, min(1.0, openness)) * 100)
        self.meter.setValue(percent)
        self.meter.setFormat(f"{openness:.2f}")


class DiagnosticsPage(QWidget):
    """Display local observations and fake-only action simulation."""

    def __init__(
        self,
        controller: VisionController,
        parent: QWidget | None = None,
        *,
        action_simulation: ActionSimulationController | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._action_simulation = action_simulation
        self._build_ui()
        self._connect_signals()
        self._clear_observation()
        self._clear_gaze_feature()
        self._clear_hand_observation()
        self._clear_temple_feature()
        self._clear_temple_proximity()
        if self._action_simulation is not None:
            self._on_simulation_snapshot(self._action_simulation.snapshot)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)

        title = QLabel("Diagnostics")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Inspect local face, uncalibrated gaze, hand, temple, gesture, and simulated "
            "action signals. "
            "Mappings run only against an in-memory fake; no mouse or keyboard input is sent."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        safe_banner = QLabel(
            "DIAGNOSTIC TRACE · Fake actions are always shown · "
            "Check the persistent bar for Live Input state"
        )
        safe_banner.setObjectName("safeBanner")
        safe_banner.setWordWrap(True)

        self._face_panel = self._build_face_panel()
        self._hand_panel = self._build_hand_panel()
        self._event_panel = self._build_event_panel()
        self._face_panel.setMinimumHeight(410)
        self._hand_panel.setMinimumHeight(330)

        panel_container = QWidget()
        panel_container.setObjectName("diagnosticsPanelContainer")
        self._panel_grid = QGridLayout(panel_container)
        self._panel_grid.setContentsMargins(0, 0, 0, 0)
        self._panel_grid.setSpacing(16)
        self._compact_panels: bool | None = None
        self._arrange_panels(self.width())

        panel_scroll = QScrollArea()
        panel_scroll.setObjectName("diagnosticsPanelScroll")
        panel_scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel_scroll.setWidget(panel_container)

        root.addWidget(title)
        root.addWidget(description)
        root.addWidget(safe_banner)
        root.addWidget(panel_scroll, stretch=1)

    def _arrange_panels(self, width: int) -> None:
        compact = width < _COMPACT_PANEL_BREAKPOINT
        if compact is self._compact_panels:
            return
        self._compact_panels = compact
        for panel in (self._face_panel, self._hand_panel, self._event_panel):
            self._panel_grid.removeWidget(panel)
        for column in range(3):
            self._panel_grid.setColumnStretch(column, 0)
        for row in range(2):
            self._panel_grid.setRowStretch(row, 0)

        if compact:
            self._panel_grid.addWidget(self._face_panel, 0, 0)
            self._panel_grid.addWidget(self._hand_panel, 0, 1)
            self._panel_grid.addWidget(self._event_panel, 1, 0, 1, 2)
            self._panel_grid.setColumnStretch(0, 1)
            self._panel_grid.setColumnStretch(1, 1)
            self._panel_grid.setRowStretch(1, 1)
            self._event_panel.setMinimumHeight(460)
        else:
            self._panel_grid.addWidget(self._face_panel, 0, 0)
            self._panel_grid.addWidget(self._hand_panel, 0, 1)
            self._panel_grid.addWidget(self._event_panel, 0, 2)
            for column in range(3):
                self._panel_grid.setColumnStretch(column, 1)
            self._panel_grid.setRowStretch(0, 1)
            self._event_panel.setMinimumHeight(0)

        self._panel_grid.invalidate()
        self._panel_grid.activate()
        container = self._panel_grid.parentWidget()
        if container is not None:
            container.updateGeometry()

    def _build_face_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        heading = QLabel("Face & gaze observations")
        heading.setObjectName("panelTitle")
        heading.setWordWrap(True)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._pipeline_value = QLabel("Stopped")
        self._face_value = QLabel("Not detected")
        self._inference_fps_value = QLabel("—")
        self._latency_value = QLabel("—")
        self._sequence_value = QLabel("—")
        self._gaze_status_value = QLabel("Unavailable")
        self._gaze_status_value.setObjectName("gazeFeatureStatusValue")
        self._gaze_horizontal_value = QLabel("—")
        self._gaze_horizontal_value.setObjectName("gazeHorizontalValue")
        self._gaze_vertical_value = QLabel("—")
        self._gaze_vertical_value.setObjectName("gazeVerticalValue")
        form.addRow("Pipeline", self._pipeline_value)
        form.addRow("Face", self._face_value)
        form.addRow("Inference FPS", self._inference_fps_value)
        form.addRow("Latency", self._latency_value)
        form.addRow("Frame", self._sequence_value)
        form.addRow("Gaze feature", self._gaze_status_value)
        form.addRow("Eye-relative X", self._gaze_horizontal_value)
        form.addRow("Eye-relative Y", self._gaze_vertical_value)

        self._left_eye = EyeMeter("Left eye openness")
        self._right_eye = EyeMeter("Right eye openness")
        layout.addWidget(heading)
        layout.addLayout(form)
        layout.addWidget(self._left_eye)
        layout.addWidget(self._right_eye)
        gaze_note = QLabel("Eye-relative features are uncalibrated and are not screen coordinates.")
        gaze_note.setObjectName("mutedText")
        gaze_note.setWordWrap(True)
        layout.addWidget(gaze_note)
        layout.addStretch(1)
        return panel

    def _build_hand_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        heading = QLabel("Hand & temple features")
        heading.setObjectName("panelTitle")
        heading.setWordWrap(True)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._hand_pipeline_value = QLabel("Stopped")
        self._hand_count_value = QLabel("0")
        self._hand_count_value.setObjectName("handCountValue")
        self._hand_fps_value = QLabel("—")
        self._hand_latency_value = QLabel("—")
        self._temple_status_value = QLabel("Unavailable")
        self._left_temple_state_value = QLabel("Unknown")
        self._left_temple_state_value.setObjectName("leftTempleStateValue")
        self._right_temple_state_value = QLabel("Unknown")
        self._right_temple_state_value.setObjectName("rightTempleStateValue")
        self._left_temple_value = QLabel("—")
        self._left_temple_value.setObjectName("leftTempleValue")
        self._right_temple_value = QLabel("—")
        self._right_temple_value.setObjectName("rightTempleValue")
        form.addRow("Pipeline", self._hand_pipeline_value)
        form.addRow("Hands", self._hand_count_value)
        form.addRow("Inference FPS", self._hand_fps_value)
        form.addRow("Latency", self._hand_latency_value)
        form.addRow("Feature state", self._temple_status_value)
        form.addRow("Left state", self._left_temple_state_value)
        form.addRow("Right state", self._right_temple_state_value)
        form.addRow("Left ratio", self._left_temple_value)
        form.addRow("Right ratio", self._right_temple_value)
        note = QLabel("Ratio = fingertip distance ÷ measured face width")
        note.setObjectName("mutedText")
        note.setWordWrap(True)

        layout.addWidget(heading)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        return panel

    def _build_event_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        heading = QLabel("Semantic events")
        heading.setObjectName("panelTitle")
        heading.setWordWrap(True)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear_events)
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        heading_row.addWidget(clear_button)

        self._event_log = QListWidget()
        self._event_log.setObjectName("eventLog")
        self._event_log.setAccessibleName("Recent semantic gesture events")
        self._event_log.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._event_log.setTextElideMode(Qt.TextElideMode.ElideRight)
        empty = QLabel("Semantic events appear here; their action mappings are simulated below.")
        empty.setObjectName("mutedText")
        empty.setWordWrap(True)

        dispatch_form = QFormLayout()
        dispatch_form.setHorizontalSpacing(12)
        dispatch_form.setVerticalSpacing(6)
        dispatch_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self._dispatch_state_value = QLabel("Disconnected")
        self._dispatch_state_value.setObjectName("dispatchStateValue")
        self._dispatch_profile_value = QLabel("—")
        self._dispatch_profile_value.setObjectName("dispatchProfileValue")
        self._dispatch_holds_value = QLabel("None")
        self._dispatch_holds_value.setObjectName("dispatchHoldsValue")
        self._dispatch_last_value = QLabel("No events")
        self._dispatch_last_value.setObjectName("dispatchLastResultValue")
        self._dispatch_last_value.setWordWrap(True)
        self._dispatch_fault_value = QLabel("None")
        self._dispatch_fault_value.setObjectName("dispatchFaultValue")
        self._dispatch_fault_value.setWordWrap(True)
        dispatch_form.addRow("Simulation", self._dispatch_state_value)
        dispatch_form.addRow("Profile", self._dispatch_profile_value)
        dispatch_form.addRow("Active holds", self._dispatch_holds_value)
        dispatch_form.addRow("Last result", self._dispatch_last_value)
        dispatch_form.addRow("Fault", self._dispatch_fault_value)

        simulation_heading = QLabel("Simulated primitive trace (fake only)")
        simulation_heading.setObjectName("panelTitle")
        simulation_heading.setWordWrap(True)
        self._simulation_log = QListWidget()
        self._simulation_log.setObjectName("simulatedActionLog")
        self._simulation_log.setAccessibleName("Recent fake-only action results")
        self._simulation_log.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._simulation_log.setTextElideMode(Qt.TextElideMode.ElideRight)

        layout.addLayout(heading_row)
        layout.addWidget(empty)
        layout.addWidget(self._event_log, stretch=1)
        layout.addLayout(dispatch_form)
        layout.addWidget(simulation_heading)
        layout.addWidget(self._simulation_log, stretch=1)
        return panel

    def _connect_signals(self) -> None:
        self._controller.observation_changed.connect(self._on_observation)
        self._controller.observation_cleared.connect(self._clear_observation)
        self._controller.gaze_feature_changed.connect(self._on_gaze_feature)
        self._controller.gaze_feature_cleared.connect(self._clear_gaze_feature)
        self._controller.health_changed.connect(self._on_health)
        self._controller.hand_observation_changed.connect(self._on_hand_observation)
        self._controller.hand_observation_cleared.connect(self._clear_hand_observation)
        self._controller.hand_health_changed.connect(self._on_hand_health)
        self._controller.temple_feature_changed.connect(self._on_temple_feature)
        self._controller.temple_feature_cleared.connect(self._clear_temple_feature)
        self._controller.temple_proximity_changed.connect(self._on_temple_proximity)
        self._controller.temple_proximity_cleared.connect(self._clear_temple_proximity)
        self._controller.event_detected.connect(self._on_event)
        if self._action_simulation is not None:
            self._action_simulation.snapshot_changed.connect(self._on_simulation_snapshot)
            self._action_simulation.report_emitted.connect(self._on_simulation_report)
            self._action_simulation.input_call_emitted.connect(self._on_simulated_input)

    @Slot(object)
    def _on_observation(self, payload: object) -> None:
        observation = face_observation(payload)
        self._face_value.setText("Detected" if observation.face_detected else "Not detected")
        self._sequence_value.setText(str(observation.source_sequence))
        self._left_eye.set_openness(observation.left_eye_openness)
        self._right_eye.set_openness(observation.right_eye_openness)

    @Slot(object)
    def _on_health(self, payload: object) -> None:
        health = vision_health(payload)
        self._pipeline_value.setText(health.status.value.capitalize())
        self._face_value.setText("Detected" if health.face_detected else "Not detected")
        self._inference_fps_value.setText(
            f"{health.inference_fps:.1f}" if health.inference_fps > 0 else "—"
        )
        self._latency_value.setText(
            f"{health.processing_latency_ms:.1f} ms" if health.processing_latency_ms > 0 else "—"
        )

    @Slot(object)
    def _on_gaze_feature(self, payload: object) -> None:
        feature = gaze_feature_observation(payload)
        self._gaze_status_value.setText(feature.status.value.replace("_", " ").title())
        combined = feature.combined
        self._gaze_horizontal_value.setText(
            f"{combined.horizontal:.3f}" if feature.ready and combined is not None else "—"
        )
        self._gaze_vertical_value.setText(
            f"{combined.vertical:.3f}" if feature.ready and combined is not None else "—"
        )

    @Slot(object)
    def _on_hand_observation(self, payload: object) -> None:
        observation = hand_observation(payload)
        self._hand_count_value.setText(str(len(observation.hands)))

    @Slot(object)
    def _on_hand_health(self, payload: object) -> None:
        health = hand_vision_health(payload)
        self._hand_pipeline_value.setText(health.status.value.capitalize())
        self._hand_count_value.setText(str(health.hand_count))
        self._hand_fps_value.setText(
            f"{health.inference_fps:.1f}" if health.inference_fps > 0 else "—"
        )
        self._hand_latency_value.setText(
            f"{health.processing_latency_ms:.1f} ms" if health.processing_latency_ms > 0 else "—"
        )

    @Slot(object)
    def _on_temple_feature(self, payload: object) -> None:
        observation = temple_feature_observation(payload)
        self._temple_status_value.setText(observation.status.value.replace("_", " ").title())
        left = observation.proximity(HandSide.LEFT)
        right = observation.proximity(HandSide.RIGHT)
        self._left_temple_value.setText(f"{left.distance_ratio:.3f}" if left is not None else "—")
        self._right_temple_value.setText(
            f"{right.distance_ratio:.3f}" if right is not None else "—"
        )

    @Slot(object)
    def _on_temple_proximity(self, payload: object) -> None:
        snapshot = temple_proximity_snapshot(payload)
        self._left_temple_state_value.setText(snapshot.left.value.capitalize())
        self._right_temple_state_value.setText(snapshot.right.value.capitalize())

    @Slot(object)
    def _on_event(self, payload: object) -> None:
        event = gesture_event(payload)
        timestamp = datetime.now().strftime("%H:%M:%S")
        label = event.type.value.replace("_TEMPLE_", " ").replace("_", " ")
        item = QListWidgetItem(
            f"{timestamp}  {label}  {event.duration_ms:.0f} ms",
        )
        item.setToolTip(
            f"{event.type.value} · source {event.source_sequence} · {event.duration_ms:.1f} ms"
        )
        self._event_log.insertItem(0, item)
        while self._event_log.count() > 50:
            self._event_log.takeItem(self._event_log.count() - 1)

    @Slot(object)
    def _on_simulation_snapshot(self, payload: object) -> None:
        snapshot = simulation_snapshot(payload)
        self._dispatch_state_value.setText(snapshot.state.value.capitalize())
        profile_name = snapshot.profile_name
        self._dispatch_profile_value.setText(_elide_middle(profile_name))
        self._dispatch_profile_value.setToolTip(profile_name)
        holds = ", ".join(gesture.value for gesture in snapshot.active_holds)
        self._dispatch_holds_value.setText(holds or "None")
        fault = snapshot.fault
        self._dispatch_fault_value.setText(
            "None" if fault is None else f"{fault.operation}: {fault.error_type}"
        )

    @Slot(object)
    def _on_simulation_report(self, payload: object) -> None:
        report = simulation_report(payload)
        action = (report.action_type or "no action").replace("_", " ").title()
        status = report.status.value.replace("_", " ").title()
        self._dispatch_last_value.setText(f"{action} · {status}")

    @Slot(object)
    def _on_simulated_input(self, payload: object) -> None:
        call = simulation_input_call(payload)
        timestamp = datetime.now().strftime("%H:%M:%S")
        operation = call.operation.replace("_", " ").title()
        arguments = ", ".join(
            str(getattr(argument, "value", argument)) for argument in call.arguments
        )
        suffix = f" · {arguments}" if arguments else ""
        item = QListWidgetItem(f"{timestamp}  {operation}{suffix}")
        item.setToolTip(f"FakeInputExecutor.{call.operation}{call.arguments!r}")
        self._simulation_log.insertItem(0, item)
        while self._simulation_log.count() > 50:
            self._simulation_log.takeItem(self._simulation_log.count() - 1)

    @Slot()
    def _clear_observation(self) -> None:
        self._face_value.setText("Not detected")
        self._sequence_value.setText("—")
        self._left_eye.set_openness(None)
        self._right_eye.set_openness(None)

    @Slot()
    def _clear_gaze_feature(self) -> None:
        self._gaze_status_value.setText("Unavailable")
        self._gaze_horizontal_value.setText("—")
        self._gaze_vertical_value.setText("—")

    @Slot()
    def _clear_hand_observation(self) -> None:
        self._hand_count_value.setText("0")

    @Slot()
    def _clear_temple_feature(self) -> None:
        self._temple_status_value.setText("Unavailable")
        self._left_temple_value.setText("—")
        self._right_temple_value.setText("—")

    @Slot()
    def _clear_temple_proximity(self) -> None:
        self._left_temple_state_value.setText("Unknown")
        self._right_temple_state_value.setText("Unknown")

    @Slot()
    def _clear_events(self) -> None:
        self._event_log.clear()
        self._simulation_log.clear()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Switch panel composition at a page-width breakpoint."""
        super().resizeEvent(event)
        self._arrange_panels(event.size().width())


def _elide_middle(value: str) -> str:
    """Bound unbroken profile labels while keeping both identifying ends."""
    if len(value) <= _MAX_PROFILE_DISPLAY_CHARS:
        return value
    visible_characters = _MAX_PROFILE_DISPLAY_CHARS - 1
    prefix_length = (visible_characters + 1) // 2
    suffix_length = visible_characters // 2
    return f"{value[:prefix_length]}…{value[-suffix_length:]}"
