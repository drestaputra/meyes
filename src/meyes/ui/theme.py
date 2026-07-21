"""Locked native UI tokens and generated Qt stylesheet."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    """Named visual roles from DESIGN.md."""

    canvas: str = "#F5F7FA"
    surface: str = "#FFFFFF"
    surface_subtle: str = "#EDF1F5"
    preview: str = "#0C111B"
    ink: str = "#172033"
    ink_muted: str = "#526079"
    border: str = "#CBD4E1"
    accent: str = "#1F5EFF"
    accent_hover: str = "#1748C8"
    focus: str = "#005FCC"
    success: str = "#197447"
    warning: str = "#8A5A00"
    danger: str = "#B42318"


def build_stylesheet(tokens: ThemeTokens | None = None) -> str:
    """Generate QSS from named tokens; widgets never improvise colors."""
    color = tokens or ThemeTokens()
    return f"""
        QMainWindow {{
            background: {color.canvas};
            color: {color.ink};
            font-family: "Segoe UI";
            font-size: 10pt;
        }}
        QWidget {{
            background: transparent;
            color: {color.ink};
            font-family: "Segoe UI";
            font-size: 10pt;
        }}
        QWidget#appRoot, QWidget#workspace {{
            background: {color.canvas};
        }}
        QWidget#privacyPage,
        QScrollArea#privacyScroll,
        QWidget#privacyViewport,
        QWidget#privacyContent {{
            background: {color.canvas};
        }}
        QWidget#sensitivityPage,
        QScrollArea#sensitivityScroll,
        QWidget#sensitivityViewport,
        QWidget#sensitivityContent {{
            background: {color.canvas};
        }}
        QWidget#cameraPage,
        QScrollArea#cameraPageScroll,
        QWidget#cameraPageViewport,
        QWidget#cameraPageContent {{
            background: {color.canvas};
        }}
        QMessageBox#actionConfirmationDialog {{
            background: {color.surface};
            color: {color.ink};
        }}
        QMessageBox#actionConfirmationDialog QLabel {{
            background: transparent;
            color: {color.ink};
        }}
        QMessageBox#actionConfirmationDialog QPushButton {{
            background: {color.surface};
            color: {color.ink};
        }}
        QToolTip {{
            background: {color.surface};
            color: {color.ink};
            border: 1px solid {color.border};
            padding: 4px 6px;
        }}
        QDialog#firstRunWizard {{
            background: {color.canvas};
        }}
        QWidget#calibrationPresentation {{
            background: {color.canvas};
        }}
        QFrame#calibrationPresentationHeader,
        QFrame#calibrationPresentationFooter {{
            background: {color.surface};
            border: 0;
        }}
        QFrame#calibrationPresentationHeader {{
            border-bottom: 1px solid {color.border};
        }}
        QFrame#calibrationPresentationFooter {{
            border-top: 1px solid {color.border};
        }}
        QFrame#calibrationResultPanel {{
            background: {color.surface};
            border: 1px solid {color.border};
            border-radius: 8px;
        }}
        QLabel#calibrationResultStatus {{
            color: {color.ink};
            font-size: 18pt;
            font-weight: 700;
        }}
        QLabel#calibrationResultStatus[acceptanceState="accepted"] {{
            color: {color.success};
        }}
        QLabel#calibrationResultStatus[acceptanceState="review_required"] {{
            color: {color.warning};
        }}
        QLabel#calibrationResultStatus[acceptanceState="rejected"],
        QLabel#calibrationResultStatus[acceptanceState="failed"] {{
            color: {color.danger};
        }}
        QLabel#calibrationResultMetrics {{
            background: {color.surface_subtle};
            border: 1px solid {color.border};
            border-radius: 4px;
            padding: 12px;
        }}
        QLabel#calibrationPresentationInstruction {{
            color: {color.ink};
            font-size: 12pt;
            font-weight: 700;
        }}
        QLabel#calibrationFocusTarget {{
            background: {color.surface};
            color: {color.accent};
            border: 4px solid {color.accent};
            border-radius: 16px;
            font-size: 18pt;
            font-weight: 700;
        }}
        QFrame#topBar, QFrame#safetyBar {{
            background: {color.surface};
            border-bottom: 1px solid {color.border};
        }}
        QFrame#safetyBar {{
            border-top: 1px solid {color.border};
            border-bottom: 0;
        }}
        QLabel#productName {{
            font-size: 16pt;
            font-weight: 700;
        }}
        QLabel#trackingStatus {{
            color: {color.ink_muted};
            font-weight: 700;
        }}
        QLabel#trackingStatus[cameraStatus="running"] {{
            color: {color.success};
        }}
        QLabel#trackingStatus[cameraStatus="starting"],
        QLabel#trackingStatus[cameraStatus="paused"],
        QLabel#trackingStatus[cameraStatus="recovering"],
        QLabel#trackingStatus[cameraStatus="stopping"] {{
            color: {color.warning};
        }}
        QLabel#trackingStatus[cameraStatus="error"] {{
            color: {color.danger};
        }}
        QLabel#liveSafetyStatus {{
            color: {color.success};
            font-weight: 700;
        }}
        QLabel#liveSafetyStatus[liveInputState="armed"],
        QLabel#liveSafetyStatus[liveInputState="faulted"] {{
            color: {color.danger};
        }}
        QLabel#sectionTitle {{
            font-size: 20pt;
            font-weight: 650;
        }}
        QLabel#mutedText, QLabel#activeProfileLabel {{
            color: {color.ink_muted};
        }}
        QLabel#previewPlaceholder {{
            background: {color.preview};
            color: {color.surface};
            border-radius: 8px;
            font-size: 12pt;
        }}
        QFrame#statusPanel {{
            background: {color.surface};
            border: 1px solid {color.border};
            border-radius: 8px;
        }}
        QLabel#panelTitle {{
            font-size: 12pt;
            font-weight: 650;
        }}
        QLabel#fieldLabel {{
            font-weight: 650;
        }}
        QLabel#selectedProfileLifecycleStatus {{
            background: {color.surface_subtle};
            border: 1px solid {color.border};
            border-radius: 4px;
            padding: 10px 12px;
            font-weight: 600;
        }}
        QLabel#statusValue {{
            font-weight: 650;
        }}
        QLabel#statusValue[cameraStatus="running"] {{
            color: {color.success};
        }}
        QLabel#statusValue[cameraStatus="recovering"],
        QLabel#statusValue[cameraStatus="paused"] {{
            color: {color.warning};
        }}
        QLabel#statusValue[cameraStatus="error"] {{
            color: {color.danger};
        }}
        QLabel#errorBanner {{
            background: {color.surface};
            color: {color.danger};
            border: 1px solid {color.danger};
            border-radius: 4px;
            padding: 10px 12px;
        }}
        QLabel#profileFeedback, QLabel#bindingFeedback {{
            background: {color.surface};
            border: 1px solid {color.border};
            border-radius: 4px;
            padding: 10px 12px;
        }}
        QLabel#sensitivityFeedback {{
            background: {color.surface};
            border: 1px solid {color.border};
            border-radius: 4px;
            padding: 10px 12px;
        }}
        QLabel#cameraSettingsFeedback {{
            background: {color.surface};
            border: 1px solid {color.border};
            border-radius: 4px;
            padding: 10px 12px;
        }}
        QLabel#firstRunFeedback {{
            background: {color.surface};
            color: {color.danger};
            border: 1px solid {color.danger};
            border-radius: 4px;
            padding: 10px 12px;
        }}
        QLabel#cameraSettingsFeedback[feedbackStatus="success"] {{
            color: {color.success};
            border-color: {color.success};
        }}
        QLabel#cameraSettingsFeedback[feedbackStatus="warning"],
        QLabel#cameraSettingsDirtyStatus[draftState="dirty"] {{
            color: {color.warning};
            border-color: {color.warning};
        }}
        QLabel#cameraSettingsFeedback[feedbackStatus="error"] {{
            color: {color.danger};
            border-color: {color.danger};
        }}
        QLabel#cameraSettingsDirtyStatus[draftState="clean"] {{
            color: {color.success};
        }}
        QLabel#sensitivityFeedback[feedbackStatus="success"] {{
            color: {color.success};
            border-color: {color.success};
        }}
        QLabel#sensitivityFeedback[feedbackStatus="warning"],
        QLabel#sensitivityDirtyStatus[draftState="dirty"] {{
            color: {color.warning};
            border-color: {color.warning};
        }}
        QLabel#sensitivityFeedback[feedbackStatus="error"] {{
            color: {color.danger};
            border-color: {color.danger};
        }}
        QLabel#sensitivityDirtyStatus[draftState="clean"] {{
            color: {color.success};
        }}
        QLabel#warningBanner {{
            background: {color.surface};
            color: {color.warning};
            border: 1px solid {color.warning};
            border-radius: 4px;
            padding: 10px 12px;
        }}
        QLabel#profileFeedback[feedbackStatus="warning"] {{
            color: {color.warning};
            border-color: {color.warning};
        }}
        QLabel#profileFeedback[feedbackStatus="error"] {{
            color: {color.danger};
            border-color: {color.danger};
        }}
        QLabel#bindingFeedback[feedbackStatus="error"] {{
            color: {color.danger};
            border-color: {color.danger};
        }}
        QLabel#profileFeedback[feedbackStatus="success"] {{
            color: {color.success};
            border-color: {color.success};
        }}
        QLabel#bindingFeedback[feedbackStatus="success"] {{
            color: {color.success};
            border-color: {color.success};
        }}
        QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
            background: {color.surface};
            border: 1px solid {color.border};
            border-radius: 4px;
            min-height: 36px;
            padding: 0 10px;
        }}
        QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QCheckBox:focus {{
            border: 2px solid {color.focus};
        }}
        QLineEdit[invalid="true"] {{
            border: 2px solid {color.danger};
        }}
        QCheckBox {{
            spacing: 8px;
        }}
        QListWidget#mainNavigation {{
            background: {color.surface};
            border: 0;
            border-right: 1px solid {color.border};
            outline: 0;
            padding: 12px 8px;
        }}
        QListWidget#mainNavigation::item {{
            border-radius: 4px;
            min-height: 36px;
            padding: 0 12px;
        }}
        QListWidget#mainNavigation::item:selected {{
            background: {color.surface_subtle};
            color: {color.ink};
            font-weight: 600;
        }}
        QListWidget#mainNavigation::item:focus {{
            border: 2px solid {color.focus};
        }}
        QListWidget#eventLog, QListWidget#simulatedActionLog {{
            background: {color.surface_subtle};
            border: 1px solid {color.border};
            border-radius: 4px;
            padding: 4px;
        }}
        QListWidget#eventLog::item, QListWidget#simulatedActionLog::item {{
            min-height: 32px;
            border-bottom: 1px solid {color.border};
            padding: 0 8px;
        }}
        QListWidget#profileList {{
            background: {color.surface_subtle};
            border: 1px solid {color.border};
            border-radius: 4px;
            outline: 0;
            padding: 4px;
        }}
        QListWidget#profileList::item {{
            min-height: 34px;
            border-radius: 3px;
            padding: 0 8px;
        }}
        QListWidget#profileList::item:selected {{
            background: {color.surface};
            color: {color.ink};
            font-weight: 600;
        }}
        QTableWidget#activeBindingsTable, QTableWidget#draftBindingsTable {{
            background: {color.surface};
            alternate-background-color: {color.surface_subtle};
            border: 1px solid {color.border};
            border-radius: 4px;
            gridline-color: {color.border};
        }}
        QHeaderView::section {{
            background: {color.surface_subtle};
            border: 0;
            border-bottom: 1px solid {color.border};
            padding: 8px;
            font-weight: 650;
        }}
        QFrame#bindingRow {{
            background: {color.surface_subtle};
            border: 1px solid {color.border};
            border-radius: 6px;
        }}
        QLabel#bindingRowTitle {{
            font-weight: 650;
        }}
        QLabel#bindingError,
        QLabel#draftStatus[draftState="error"] {{
            color: {color.danger};
            font-weight: 600;
        }}
        QLabel#draftStatus[draftState="dirty"] {{
            color: {color.warning};
            font-weight: 600;
        }}
        QLabel#draftStatus[draftState="clean"] {{
            color: {color.success};
            font-weight: 600;
        }}
        QLabel#safeBanner {{
            background: {color.surface};
            color: {color.success};
            border: 1px solid {color.success};
            border-radius: 4px;
            padding: 10px 12px;
            font-weight: 650;
        }}
        QLabel#liveInputStatus, QLabel#liveInputFeedback {{
            background: {color.surface};
            border: 1px solid {color.border};
            border-radius: 4px;
            padding: 10px 12px;
            font-weight: 650;
        }}
        QLabel#liveInputStatus[liveInputState="safe"] {{
            color: {color.success};
            border-color: {color.success};
        }}
        QLabel#liveInputStatus[liveInputState="armed"] {{
            color: {color.danger};
            border-color: {color.danger};
            background: {color.surface};
        }}
        QLabel#liveInputStatus[liveInputState="faulted"] {{
            color: {color.danger};
            border-color: {color.danger};
        }}
        QProgressBar {{
            background: {color.surface_subtle};
            border: 1px solid {color.border};
            border-radius: 4px;
            min-height: 26px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background: {color.accent};
            border-radius: 3px;
        }}
        QPushButton {{
            background: {color.surface};
            border: 1px solid {color.border};
            border-radius: 4px;
            min-height: 36px;
            padding: 0 16px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {color.surface_subtle};
        }}
        QPushButton:focus {{
            border: 2px solid {color.focus};
        }}
        QPushButton#primaryButton {{
            background: {color.accent};
            border-color: {color.accent};
            color: {color.surface};
            min-height: 40px;
        }}
        QPushButton[primaryAction="true"] {{
            background: {color.accent};
            border-color: {color.accent};
            color: {color.surface};
            min-height: 40px;
        }}
        QPushButton#primaryButton:hover, QPushButton[primaryAction="true"]:hover {{
            background: {color.accent_hover};
        }}
        QPushButton[dangerAction="true"] {{
            color: {color.danger};
            border-color: {color.danger};
        }}
        QPushButton[dangerAction="true"]:hover {{
            background: {color.surface_subtle};
        }}
        QPushButton:disabled,
        QPushButton#primaryButton:disabled {{
            background: {color.surface_subtle};
            border-color: {color.border};
            color: {color.ink_muted};
        }}
    """
