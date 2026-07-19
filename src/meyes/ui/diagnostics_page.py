"""Live safe-mode face, hand, temple, and gesture diagnostics."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from meyes.domain.observations import HandSide
from meyes.vision.controller import (
    VisionController,
    face_observation,
    gesture_event,
    hand_observation,
    hand_vision_health,
    temple_feature_observation,
    vision_health,
)


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
    """Display local semantic observations without executing actions."""

    def __init__(self, controller: VisionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._build_ui()
        self._connect_signals()
        self._clear_observation()
        self._clear_hand_observation()
        self._clear_temple_feature()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)

        title = QLabel("Diagnostics")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Inspect local face, hand, temple, and gesture signals. Safe mode is locked on: "
            "no mouse or keyboard input is sent."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        safe_banner = QLabel("SAFE MODE · Detection only · OS input disconnected")
        safe_banner.setObjectName("safeBanner")

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(self._build_face_panel(), stretch=1)
        columns.addWidget(self._build_hand_panel(), stretch=1)
        columns.addWidget(self._build_event_panel(), stretch=1)

        root.addWidget(title)
        root.addWidget(description)
        root.addWidget(safe_banner)
        root.addLayout(columns, stretch=1)

    def _build_face_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        heading = QLabel("Face observations")
        heading.setObjectName("panelTitle")
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self._pipeline_value = QLabel("Stopped")
        self._face_value = QLabel("Not detected")
        self._inference_fps_value = QLabel("—")
        self._latency_value = QLabel("—")
        self._sequence_value = QLabel("—")
        form.addRow("Pipeline", self._pipeline_value)
        form.addRow("Face", self._face_value)
        form.addRow("Inference FPS", self._inference_fps_value)
        form.addRow("Latency", self._latency_value)
        form.addRow("Frame", self._sequence_value)

        self._left_eye = EyeMeter("Left eye openness")
        self._right_eye = EyeMeter("Right eye openness")
        layout.addWidget(heading)
        layout.addLayout(form)
        layout.addWidget(self._left_eye)
        layout.addWidget(self._right_eye)
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
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        self._hand_pipeline_value = QLabel("Stopped")
        self._hand_count_value = QLabel("0")
        self._hand_count_value.setObjectName("handCountValue")
        self._hand_fps_value = QLabel("—")
        self._hand_latency_value = QLabel("—")
        self._temple_status_value = QLabel("Unavailable")
        self._left_temple_value = QLabel("—")
        self._left_temple_value.setObjectName("leftTempleValue")
        self._right_temple_value = QLabel("—")
        self._right_temple_value.setObjectName("rightTempleValue")
        form.addRow("Pipeline", self._hand_pipeline_value)
        form.addRow("Hands", self._hand_count_value)
        form.addRow("Inference FPS", self._hand_fps_value)
        form.addRow("Latency", self._hand_latency_value)
        form.addRow("Feature state", self._temple_status_value)
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
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear_events)
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        heading_row.addWidget(clear_button)

        self._event_log = QListWidget()
        self._event_log.setObjectName("eventLog")
        self._event_log.setAccessibleName("Recent semantic gesture events")
        empty = QLabel(
            "Events appear here. Detection and temple features do not trigger actions in Safe mode."
        )
        empty.setObjectName("mutedText")
        empty.setWordWrap(True)

        layout.addLayout(heading_row)
        layout.addWidget(empty)
        layout.addWidget(self._event_log, stretch=1)
        return panel

    def _connect_signals(self) -> None:
        self._controller.observation_changed.connect(self._on_observation)
        self._controller.observation_cleared.connect(self._clear_observation)
        self._controller.health_changed.connect(self._on_health)
        self._controller.hand_observation_changed.connect(self._on_hand_observation)
        self._controller.hand_observation_cleared.connect(self._clear_hand_observation)
        self._controller.hand_health_changed.connect(self._on_hand_health)
        self._controller.temple_feature_changed.connect(self._on_temple_feature)
        self._controller.temple_feature_cleared.connect(self._clear_temple_feature)
        self._controller.event_detected.connect(self._on_event)

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
    def _on_event(self, payload: object) -> None:
        event = gesture_event(payload)
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._event_log.insertItem(
            0,
            f"{timestamp}  {event.type.value}  {event.duration_ms:.0f} ms",
        )
        while self._event_log.count() > 50:
            self._event_log.takeItem(self._event_log.count() - 1)

    @Slot()
    def _clear_observation(self) -> None:
        self._face_value.setText("Not detected")
        self._sequence_value.setText("—")
        self._left_eye.set_openness(None)
        self._right_eye.set_openness(None)

    @Slot()
    def _clear_hand_observation(self) -> None:
        self._hand_count_value.setText("0")

    @Slot()
    def _clear_temple_feature(self) -> None:
        self._temple_status_value.setText("Unavailable")
        self._left_temple_value.setText("—")
        self._right_temple_value.setText("—")

    @Slot()
    def _clear_events(self) -> None:
        self._event_log.clear()
