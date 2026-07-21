"""Read-only privacy, storage, and live-output boundary view."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from meyes.ui.live_input import LiveInputState
from meyes.util.paths import AppPaths


class PrivacyPage(QWidget):
    """Expose the current local-data boundary without mutating user files."""

    def __init__(self, paths: AppPaths, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("privacyPage")

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("privacyScroll")
        scroll.viewport().setObjectName("privacyViewport")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAccessibleName("Privacy and local data details")
        content = QWidget()
        content.setObjectName("privacyContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        heading = QLabel("Privacy")
        heading.setObjectName("sectionTitle")
        summary = QLabel(
            "MEYES processes camera observations locally and starts with operating-system input "
            "disconnected. This view reports the current product boundary and local file locations."
        )
        summary.setObjectName("mutedText")
        summary.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(summary)

        self._live_status = QLabel()
        self._live_status.setObjectName("liveInputStatus")
        self._live_status.setAccessibleName("Current operating-system input status")
        self._live_status.setWordWrap(True)
        layout.addWidget(self._live_status)
        self.set_live_input_state(LiveInputState.SAFE)

        layout.addWidget(
            self._boundary_panel(
                "Camera and derived observations",
                "Frames stay in bounded latest-only memory for preview and local inference, then "
                "are discarded. Raw frames, landmarks, gaze features, and calibration samples are "
                "not intentionally saved or uploaded.",
                "privacyCameraBoundary",
            )
        )
        layout.addWidget(
            self._boundary_panel(
                "What is persisted",
                "Local settings and profiles, rotating lifecycle/error logs, and only an "
                "explicitly accepted calibration envelope may be stored. Live Input consent is "
                "volatile and is never restored at startup.",
                "privacyPersistenceBoundary",
            )
        )
        layout.addWidget(
            self._boundary_panel(
                "Network boundary",
                "The MEYES runtime has no OpenAI API call and no camera-frame upload path. "
                "MediaPipe may contact Google for fixes, model updates, compatibility information, "
                "or non-input metrics; use an audited offline environment when zero network access "
                "is required.",
                "privacyNetworkBoundary",
            )
        )
        layout.addWidget(
            self._boundary_panel(
                "Real Windows input",
                "Real output requires a running camera, explicit per-session modal consent, a "
                "registered emergency shortcut, clear physical inputs, and explicit arming. Camera "
                "lifecycle, profile changes, faults, shutdown, or Ctrl+Alt+Shift+F11 disarm and "
                "release state.",
                "privacyInputBoundary",
            )
        )

        locations = QFrame()
        locations.setObjectName("statusPanel")
        locations_layout = QVBoxLayout(locations)
        locations_layout.setContentsMargins(16, 14, 16, 14)
        locations_layout.setSpacing(8)
        locations_title = QLabel("Local file locations")
        locations_title.setObjectName("panelTitle")
        locations_layout.addWidget(locations_title)
        self._add_path(locations_layout, "Configuration", paths.config_file)
        self._add_path(locations_layout, "Profiles", paths.profiles_dir)
        self._add_path(locations_layout, "Accepted calibration", paths.calibration_file)
        self._add_path(locations_layout, "Rotating log", paths.log_file)
        deletion = QLabel(
            "Close MEYES before deleting local files. Calibration backup deletion has separate "
            "guarded controls; see PRIVACY.md for exact retention and recovery behavior."
        )
        deletion.setObjectName("mutedText")
        deletion.setWordWrap(True)
        locations_layout.addWidget(deletion)
        layout.addWidget(locations)
        layout.addStretch(1)

        scroll.setWidget(content)
        page_layout.addWidget(scroll)

    def set_live_input_state(self, state: LiveInputState) -> None:
        """Reflect the live-output boundary without exposing an arming control."""
        labels = {
            LiveInputState.SAFE: "SAFE MODE · operating-system input is disconnected",
            LiveInputState.ARMED: "LIVE INPUT · real operating-system output is enabled",
            LiveInputState.FAULTED: "LIVE INPUT FAULT · output is gated and tracking is paused",
            LiveInputState.CLOSED: "LIVE INPUT CLOSED · operating-system input is disconnected",
        }
        self._live_status.setText(labels[state])
        self._live_status.setProperty("liveInputState", state.value)
        self._live_status.style().unpolish(self._live_status)
        self._live_status.style().polish(self._live_status)

    @staticmethod
    def _boundary_panel(title: str, detail: str, object_name: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        panel.setAccessibleName(title)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setObjectName("panelTitle")
        body = QLabel(detail)
        body.setObjectName(object_name)
        body.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(body)
        return panel

    @staticmethod
    def _add_path(layout: QVBoxLayout, label: str, path: Path) -> None:
        heading = QLabel(label)
        heading.setObjectName("fieldLabel")
        value = QLabel(str(path))
        value.setObjectName("privacyPath")
        value.setAccessibleName(f"{label} path")
        value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        value.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(value)
