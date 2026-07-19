"""Initial native application shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from meyes.config.models import AppConfig
from meyes.ui.theme import build_stylesheet

NAVIGATION_ITEMS = (
    "Dashboard",
    "Calibration",
    "Bindings",
    "Sensitivity",
    "Camera",
    "Profiles",
    "Diagnostics",
    "Privacy",
)


class MainWindow(QMainWindow):
    """MEYES control-room shell with persistent safety status."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self.setWindowTitle("Meyes")
        self.resize(config.ui.window_width, config.ui.window_height)
        self.setMinimumSize(900, 640)
        self.setStyleSheet(build_stylesheet())
        self.setCentralWidget(self._build_shell())

    def _build_shell(self) -> QWidget:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_top_bar())
        layout.addWidget(self._build_workspace(), stretch=1)
        layout.addWidget(self._build_safety_bar())
        return root

    def _build_top_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("topBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(20)

        product = QLabel("MEYES")
        product.setObjectName("productName")
        profile = QLabel(f"Profile: {self._config.app.active_profile}")
        profile.setObjectName("mutedText")
        status = QLabel("TRACKING PAUSED")
        status.setObjectName("trackingStatus")
        resume = QPushButton("Resume tracking")
        resume.setObjectName("primaryButton")
        resume.setAccessibleName("Resume tracking")
        resume.setEnabled(False)
        resume.setToolTip("Camera controls will be available in Phase 1")

        layout.addWidget(product)
        layout.addWidget(profile)
        layout.addStretch(1)
        layout.addWidget(status)
        layout.addWidget(resume)
        return frame

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        layout = QHBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        navigation = QListWidget()
        navigation.setFixedWidth(210)
        navigation.addItems(NAVIGATION_ITEMS)
        selected_row = max(0, NAVIGATION_ITEMS.index(self._config.ui.selected_page))
        navigation.setCurrentRow(selected_row)
        navigation.setAccessibleName("Main navigation")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 28, 32, 28)
        content_layout.setSpacing(16)

        title = QLabel("Camera dashboard")
        title.setObjectName("sectionTitle")
        description = QLabel(
            "Camera capture is not running yet. The next iteration adds device selection, "
            "preview, health, and lifecycle controls."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        preview = QLabel("Camera preview will appear here")
        preview.setObjectName("previewPlaceholder")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview.setMinimumSize(480, 320)

        content_layout.addWidget(title)
        content_layout.addWidget(description)
        content_layout.addWidget(preview, stretch=1)
        layout.addWidget(navigation)
        layout.addWidget(content, stretch=1)
        return workspace

    def _build_safety_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("safetyBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(24, 10, 24, 10)
        shortcut = QLabel("Ctrl + Alt + F12 pauses tracking immediately")
        local = QLabel("Camera processing stays on this device")
        local.setObjectName("mutedText")
        layout.addWidget(shortcut)
        layout.addStretch(1)
        layout.addWidget(local)
        return frame
