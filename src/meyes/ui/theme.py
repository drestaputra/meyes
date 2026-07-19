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
        QMainWindow, QWidget {{
            background: {color.canvas};
            color: {color.ink};
            font-family: "Segoe UI Variable", "Segoe UI";
            font-size: 10pt;
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
            color: {color.warning};
            font-weight: 700;
        }}
        QLabel#sectionTitle {{
            font-size: 20pt;
            font-weight: 650;
        }}
        QLabel#mutedText {{
            color: {color.ink_muted};
        }}
        QLabel#previewPlaceholder {{
            background: {color.preview};
            color: {color.surface};
            border-radius: 8px;
            font-size: 12pt;
        }}
        QListWidget {{
            background: {color.surface};
            border: 0;
            border-right: 1px solid {color.border};
            outline: 0;
            padding: 12px 8px;
        }}
        QListWidget::item {{
            border-radius: 4px;
            min-height: 36px;
            padding: 0 12px;
        }}
        QListWidget::item:selected {{
            background: {color.surface_subtle};
            color: {color.ink};
            font-weight: 600;
        }}
        QListWidget::item:focus {{
            border: 2px solid {color.focus};
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
        QPushButton#primaryButton:hover {{
            background: {color.accent_hover};
        }}
    """
