"""Safe, non-capturing first-run orientation dialog."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from meyes.ui.confirmation_dialog import confirm_action

CompleteFirstRun = Callable[[], bool]


class FirstRunWizard(QDialog):
    """Explain the safety boundary before recording durable setup completion."""

    def __init__(
        self,
        complete_first_run: CompleteFirstRun,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not callable(complete_first_run):
            raise TypeError("complete_first_run must be callable")
        self._complete_first_run = complete_first_run
        self.setObjectName("firstRunWizard")
        self.setWindowTitle("Welcome to MEYES")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumSize(640, 500)
        self.resize(720, 560)
        self._build_ui()
        self._render_step()

    @property
    def current_step(self) -> int:
        """Return the zero-based orientation step for deterministic UI tests."""

        return self._pages.currentIndex()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        self._progress = QLabel()
        self._progress.setObjectName("mutedText")
        self._progress.setAccessibleName("First-run setup progress")
        self._pages = QStackedWidget()
        self._pages.setObjectName("firstRunPages")
        self._pages.addWidget(
            self._step(
                "Welcome to local-first control",
                "MEYES is an assistive productivity prototype, not a medical device. Face, hand, "
                "and gaze observations are processed locally from an ordinary webcam. The runtime "
                "has no OpenAI API dependency or camera-frame upload path.",
                (
                    "Camera capture does not start from this wizard.",
                    "Raw frames, landmarks, and calibration samples are not intentionally saved.",
                    "You can inspect the full boundary later on the Privacy page.",
                ),
            )
        )
        self._pages.addWidget(
            self._step(
                "Verify before tracking",
                "Dashboard owns camera selection, preview, and start/pause/stop. Begin with a "
                "stable preview in appropriate lighting, and only capture people who know they "
                "are visible.",
                (
                    "Camera permission may be requested by Windows on first start.",
                    "Diagnostics shows local face, hand, gesture, and cursor-candidate state.",
                    "Calibration acceptance defaults to Review Required without evidence limits.",
                ),
            )
        )
        final_page = self._step(
            "Safe Mode is the default",
            "Camera tracking and real Windows output are separate decisions. Live Input requires "
            "explicit modal consent every session, a registered emergency shortcut, clear physical "
            "inputs, and an explicit Arm action.",
            (
                "Startup and camera start never arm operating-system input.",
                "Ctrl+Alt+Shift+F11 returns MEYES to Safe Mode.",
                "Camera lifecycle, profile changes, faults, and shutdown also disarm and release.",
            ),
        )
        final_layout = final_page.layout()
        assert isinstance(final_layout, QVBoxLayout)
        acknowledgement = QLabel(
            "Finishing records only that this safety orientation was completed. Live Input remains "
            "optional and requires a separate confirmation for every armed session."
        )
        acknowledgement.setObjectName("firstRunSafetyAcknowledgementNotice")
        acknowledgement.setWordWrap(True)
        final_layout.addWidget(acknowledgement)
        self._pages.addWidget(final_page)

        self._feedback = QLabel()
        self._feedback.setObjectName("firstRunFeedback")
        self._feedback.setWordWrap(True)
        self._feedback.hide()

        buttons = QHBoxLayout()
        self._not_now = QPushButton("Not now")
        self._not_now.setObjectName("firstRunNotNowButton")
        self._back = QPushButton("Back")
        self._back.setObjectName("firstRunBackButton")
        self._next = QPushButton("Next")
        self._next.setObjectName("firstRunNextButton")
        self._next.setProperty("primaryAction", True)
        self._finish = QPushButton("Finish setup")
        self._finish.setObjectName("firstRunFinishButton")
        self._finish.setProperty("primaryAction", True)
        buttons.addWidget(self._not_now)
        buttons.addStretch(1)
        buttons.addWidget(self._back)
        buttons.addWidget(self._next)
        buttons.addWidget(self._finish)

        layout.addWidget(self._progress)
        layout.addWidget(self._pages, stretch=1)
        layout.addWidget(self._feedback)
        layout.addLayout(buttons)

        self._not_now.clicked.connect(self.reject)
        self._back.clicked.connect(self._previous_step)
        self._next.clicked.connect(self._next_step)
        self._finish.clicked.connect(self._finish_setup)

    @staticmethod
    def _step(title: str, description: str, points: tuple[str, ...]) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        body = QLabel(description)
        body.setObjectName("mutedText")
        body.setWordWrap(True)
        panel = QFrame()
        panel.setObjectName("statusPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        panel_layout.setSpacing(10)
        for point in points:
            label = QLabel(f"• {point}")
            label.setWordWrap(True)
            panel_layout.addWidget(label)
        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addWidget(panel)
        layout.addStretch(1)
        return page

    def _render_step(self) -> None:
        index = self._pages.currentIndex()
        final = index == self._pages.count() - 1
        self._progress.setText(f"Orientation {index + 1} of {self._pages.count()}")
        self._back.setEnabled(index > 0)
        self._next.setVisible(not final)
        self._finish.setVisible(final)
        self._finish.setEnabled(final)

    def _previous_step(self) -> None:
        self._pages.setCurrentIndex(max(0, self._pages.currentIndex() - 1))
        self._render_step()

    def _next_step(self) -> None:
        self._pages.setCurrentIndex(min(self._pages.count() - 1, self._pages.currentIndex() + 1))
        self._render_step()

    def _finish_setup(self) -> None:
        if not confirm_action(
            self,
            title="Finish safety orientation?",
            message=(
                "Record this orientation as complete? MEYES will still start in Safe Mode, and "
                "Live Input remains optional with separate confirmation for every armed session."
            ),
            confirm_label="Finish setup",
        ):
            return
        if self._complete_first_run():
            self.accept()
            return
        self._feedback.setText(
            "Setup completion could not be saved. MEYES remains in Safe Mode; retry or choose "
            "Not now."
        )
        self._feedback.setProperty("feedbackStatus", "error")
        self._feedback.show()
