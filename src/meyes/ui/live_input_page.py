"""Persistent consent and safety controls for real Windows input."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from meyes.input.windows_safety import EMERGENCY_HOTKEY_LABEL
from meyes.ui.live_input import (
    LIVE_INPUT_CONSENT_PHRASE,
    LiveInputController,
    LiveInputSnapshot,
    LiveInputState,
)

WindowIdProvider = Callable[[], int]


class LiveInputPage(QWidget):
    """Expose a deliberate, non-persistent transition out of Safe Mode."""

    def __init__(
        self,
        controller: LiveInputController,
        window_id_provider: WindowIdProvider,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(controller, LiveInputController):
            raise TypeError("Expected LiveInputController")
        if not callable(window_id_provider):
            raise TypeError("window_id_provider must be callable")
        self._controller = controller
        self._window_id_provider = window_id_provider
        self._tracking_available = False
        self._build_ui()
        self._controller.snapshot_changed.connect(self._on_snapshot_changed)
        self._consent.textChanged.connect(self._update_controls)
        self._arm_button.clicked.connect(self._arm)
        self._safe_button.clicked.connect(self._return_to_safe_mode)
        self._render(self._controller.snapshot)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("liveInputPageScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title = QLabel("Live Input")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Opt in to real Windows mouse and keyboard output for this application session. "
            "Safe Mode remains the default and is restored after every disarm."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        self._status = QLabel()
        self._status.setObjectName("liveInputStatus")
        self._status.setAccessibleName("Live Input status")
        self._status.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self._status)
        layout.addWidget(self._build_safety_panel())
        layout.addWidget(self._build_consent_panel())
        layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll)

    def _build_safety_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        heading = QLabel("Before you arm")
        heading.setObjectName("panelTitle")
        details = QLabel(
            f"1. Start the camera and verify stable gesture diagnostics.\n"
            f"2. Release physical mouse buttons and Ctrl, Alt, Shift, and Windows keys.\n"
            f"3. Keep {EMERGENCY_HOTKEY_LABEL} available at all times.\n"
            "4. Live Input may be blocked when the target app runs at a higher integrity level."
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        local = QLabel(
            "The opt-in is volatile: it is not stored in configuration, profile files, or logs."
        )
        local.setObjectName("mutedText")
        local.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(details)
        layout.addWidget(local)
        return panel

    def _build_consent_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        heading = QLabel("Per-session consent")
        heading.setObjectName("panelTitle")
        instruction = QLabel(
            f"Type {LIVE_INPUT_CONSENT_PHRASE} exactly. Arming is available only while the "
            "camera is running."
        )
        instruction.setWordWrap(True)
        self._consent = QLineEdit()
        self._consent.setObjectName("liveInputConsent")
        self._consent.setAccessibleName("Exact phrase to enable Live Input")
        self._consent.setPlaceholderText(LIVE_INPUT_CONSENT_PHRASE)
        self._consent.setMaxLength(len(LIVE_INPUT_CONSENT_PHRASE))

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self._arm_button = QPushButton("Arm Live Input")
        self._arm_button.setObjectName("armLiveInputButton")
        self._arm_button.setAccessibleName("Arm real Windows input")
        self._arm_button.setProperty("dangerAction", True)
        self._safe_button = QPushButton("Return to Safe Mode")
        self._safe_button.setObjectName("disarmLiveInputButton")
        self._safe_button.setAccessibleName("Disarm and release real Windows input")
        buttons.addWidget(self._arm_button)
        buttons.addWidget(self._safe_button)
        buttons.addStretch(1)

        self._feedback = QLabel()
        self._feedback.setObjectName("liveInputFeedback")
        self._feedback.setAccessibleName("Live Input lifecycle result")
        self._feedback.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(instruction)
        layout.addWidget(self._consent)
        layout.addLayout(buttons)
        layout.addWidget(self._feedback)
        return panel

    def set_tracking_available(self, available: bool) -> None:
        """Gate new live sessions against the actual camera lifecycle."""
        if not isinstance(available, bool):
            raise TypeError("available must be a bool")
        self._tracking_available = available
        self._update_controls()

    @Slot()
    def _arm(self) -> None:
        try:
            window_id = self._window_id_provider()
        except Exception as error:
            self._feedback.setText(f"Window handle unavailable ({type(error).__name__}).")
            return
        phrase = self._consent.text()
        self._consent.clear()
        result = self._controller.arm(phrase, window_id)
        self._feedback.setText(result.message)

    @Slot()
    def _return_to_safe_mode(self) -> None:
        result = self._controller.disarm("user request")
        self._consent.clear()
        self._feedback.setText(result.message)

    @Slot(object)
    def _on_snapshot_changed(self, payload: object) -> None:
        if isinstance(payload, LiveInputSnapshot):
            self._render(payload)

    @Slot()
    def _update_controls(self) -> None:
        snapshot = self._controller.snapshot
        can_arm = (
            snapshot.state is LiveInputState.SAFE
            and snapshot.platform_supported
            and self._tracking_available
            and self._consent.text() == LIVE_INPUT_CONSENT_PHRASE
        )
        self._arm_button.setEnabled(can_arm)
        self._safe_button.setEnabled(
            snapshot.state in {LiveInputState.ARMED, LiveInputState.FAULTED}
        )
        self._safe_button.setText(
            "Retry cleanup" if snapshot.state is LiveInputState.FAULTED else "Return to Safe Mode"
        )
        self._consent.setEnabled(snapshot.state is LiveInputState.SAFE)

    def _render(self, snapshot: LiveInputSnapshot) -> None:
        labels = {
            LiveInputState.SAFE: "SAFE MODE · OS input disconnected",
            LiveInputState.ARMED: "LIVE INPUT ARMED · REAL OS OUTPUT ENABLED",
            LiveInputState.FAULTED: "LIVE INPUT FAULTED · TRACKING MUST REMAIN PAUSED",
            LiveInputState.CLOSED: "LIVE INPUT CLOSED",
        }
        text = labels[snapshot.state]
        if not snapshot.platform_supported:
            text = "UNAVAILABLE · Live Input requires Windows 10 or Windows 11"
        self._status.setText(text)
        self._status.setProperty("liveInputState", snapshot.state.value)
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)
        self._feedback.setText(snapshot.message)
        self._update_controls()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Never allow page destruction to strand an armed native event filter."""
        if self._controller.state is not LiveInputState.CLOSED:
            self._controller.disarm("Live Input page close")
        super().closeEvent(event)
