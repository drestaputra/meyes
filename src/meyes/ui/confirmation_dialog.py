"""Reusable explicit action confirmation with a safe cancel default."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def confirm_action(
    parent: QWidget,
    *,
    title: str,
    message: str,
    confirm_label: str,
    destructive: bool = False,
) -> bool:
    """Return true only when the user selects the named modal confirmation action."""

    if not all(
        isinstance(value, str) and value.strip() for value in (title, message, confirm_label)
    ):
        raise ValueError("Confirmation title, message, and action label must be non-empty")
    if not isinstance(destructive, bool):
        raise TypeError("destructive must be a bool")
    dialog = QMessageBox(parent)
    dialog.setObjectName("actionConfirmationDialog")
    dialog.setWindowTitle(title.strip())
    dialog.setText(message.strip())
    dialog.setIcon(QMessageBox.Icon.Warning if destructive else QMessageBox.Icon.Question)
    confirm_button = dialog.addButton(confirm_label.strip(), QMessageBox.ButtonRole.AcceptRole)
    confirm_button.setObjectName("confirmActionButton")
    cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    cancel_button.setObjectName("cancelActionButton")
    dialog.setDefaultButton(cancel_button)
    dialog.setEscapeButton(cancel_button)
    dialog.exec()
    return dialog.clickedButton() is confirm_button
