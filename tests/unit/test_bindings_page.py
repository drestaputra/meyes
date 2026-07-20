"""Native isolated binding editor UI tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot

from meyes.bindings.defaults import default_profile, disabled_profile
from meyes.bindings.editor import EditableActionKind
from meyes.bindings.models import BindableGesture
from meyes.bindings.presentation import gesture_label
from meyes.bindings.repository import BindingProfileRepository
from meyes.domain.actions import DisabledAction, KeyboardKeyAction, KeyName
from meyes.ui.binding_editor_controller import BindingEditorController
from meyes.ui.bindings_page import BindingsPage
from meyes.ui.theme import build_stylesheet
from meyes.util.paths import AppPaths

WidgetT = TypeVar("WidgetT", bound=QWidget)


@dataclass(slots=True)
class BindingPageHarness:
    page: BindingsPage
    controller: BindingEditorController
    repository: BindingProfileRepository
    paths: AppPaths


def _binding_page(qtbot: QtBot, tmp_path: Path) -> BindingPageHarness:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    controller = BindingEditorController(default_profile(), repository=repository)
    page = BindingsPage(controller)
    page.setStyleSheet(build_stylesheet())
    qtbot.addWidget(page)
    return BindingPageHarness(page, controller, repository, paths)


def _required_child(parent: QWidget, widget_type: type[WidgetT], name: str) -> WidgetT:
    child = parent.findChild(widget_type, name)
    assert child is not None, f"missing {widget_type.__name__}#{name}"
    return child


def _combo(page: BindingsPage, gesture: BindableGesture) -> QComboBox:
    return _required_child(page, QComboBox, f"bindingAction_{gesture.value}")


def _parameters(page: BindingsPage, gesture: BindableGesture) -> QLineEdit:
    return _required_child(page, QLineEdit, f"bindingParameters_{gesture.value}")


def _reset(page: BindingsPage, gesture: BindableGesture) -> QPushButton:
    return _required_child(page, QPushButton, f"resetBinding_{gesture.value}")


def _select_kind(combo: QComboBox, kind: EditableActionKind) -> None:
    index = combo.findData(kind.value)
    assert index >= 0, f"missing editor kind {kind.value}"
    combo.setCurrentIndex(index)


def _table_text(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


def test_page_renders_six_accessible_rows_and_last_valid_preview(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _binding_page(qtbot, tmp_path)
    preview = _required_child(harness.page, QTableWidget, "draftBindingsTable")
    source = _required_child(harness.page, QLabel, "draftSourceValue")
    active = _required_child(harness.page, QLabel, "draftActiveValue")
    copy_name = _required_child(harness.page, QLineEdit, "bindingCopyName")
    save = _required_child(harness.page, QPushButton, "saveBindingDraftButton")

    assert source.text() == "Default"
    assert active.text() == "Default"
    assert preview.rowCount() == len(BindableGesture) == 6
    assert preview.columnCount() == 2
    assert _table_text(preview, 0, 0) == "Left wink"
    assert "Mouse click" in _table_text(preview, 0, 1)
    assert preview.accessibleName() == "Isolated draft binding preview"
    assert copy_name.accessibleName() == "New profile name for binding draft"
    assert save.accessibleName() == "Save binding draft as a new inactive profile"
    assert not save.isEnabled()

    for gesture in BindableGesture:
        combo = _combo(harness.page, gesture)
        parameters = _parameters(harness.page, gesture)
        reset = _reset(harness.page, gesture)
        assert combo.accessibleName() == f"Action for {gesture_label(gesture)}"
        assert parameters.accessibleName() == f"Parameters for {gesture_label(gesture)}"
        assert reset.accessibleName() == f"Reset {gesture_label(gesture)} binding"
        assert not reset.isEnabled()

    assert _combo(harness.page, BindableGesture.LEFT_WINK).count() == 10
    assert _combo(harness.page, BindableGesture.LEFT_TEMPLE_HOLD).count() == 12


def test_valid_row_edit_updates_preview_and_enables_save(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _binding_page(qtbot, tmp_path)
    gesture = BindableGesture.LEFT_WINK
    combo = _combo(harness.page, gesture)
    parameters = _parameters(harness.page, gesture)
    preview = _required_child(harness.page, QTableWidget, "draftBindingsTable")
    name = _required_child(harness.page, QLineEdit, "bindingCopyName")
    save = _required_child(harness.page, QPushButton, "saveBindingDraftButton")

    _select_kind(combo, EditableActionKind.KEYBOARD_KEY)
    parameters.setText("ENTER")
    name.setText("Keyboard profile")

    assert harness.controller.state.draft_profile.bindings[gesture] == KeyboardKeyAction(
        key=KeyName.ENTER
    )
    assert harness.controller.state.dirty
    assert harness.controller.state.errors == ()
    assert _table_text(preview, 0, 1) == "Keyboard key · ENTER"
    assert save.isEnabled()


def test_invalid_parameters_stay_inline_and_do_not_replace_preview(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _binding_page(qtbot, tmp_path)
    gesture = BindableGesture.LEFT_WINK
    combo = _combo(harness.page, gesture)
    parameters = _parameters(harness.page, gesture)
    row = combo.parentWidget()
    assert row is not None
    error = _required_child(row, QLabel, "bindingError")
    preview = _required_child(harness.page, QTableWidget, "draftBindingsTable")
    name = _required_child(harness.page, QLineEdit, "bindingCopyName")
    save = _required_child(harness.page, QPushButton, "saveBindingDraftButton")

    name.setText("Invalid draft")
    _select_kind(combo, EditableActionKind.MOUSE_SCROLL)
    parameters.setText("0")

    assert error.isHidden() is False
    assert "non-zero" in error.text()
    assert parameters.property("invalid") is True
    assert _table_text(preview, 0, 1) == "Mouse click · left"
    assert not save.isEnabled()

    _reset(harness.page, gesture).click()

    assert error.isHidden()
    assert parameters.property("invalid") is False
    assert combo.currentData() == EditableActionKind.MOUSE_CLICK.value
    assert parameters.text() == "left"
    assert not harness.controller.state.dirty


def test_save_as_copy_is_explicitly_inactive_and_refreshes_source_state(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _binding_page(qtbot, tmp_path)
    combo = _combo(harness.page, BindableGesture.LEFT_WINK)
    name = _required_child(harness.page, QLineEdit, "bindingCopyName")
    save = _required_child(harness.page, QPushButton, "saveBindingDraftButton")
    feedback = _required_child(harness.page, QLabel, "bindingFeedback")
    source = _required_child(harness.page, QLabel, "draftSourceValue")
    active = _required_child(harness.page, QLabel, "draftActiveValue")
    scroll = _required_child(harness.page, QScrollArea, "bindingsPageScroll")

    _select_kind(combo, EditableActionKind.DISABLED)
    name.setText("Quiet Copy")
    harness.page.setFixedSize(690, 640)
    harness.page.show()
    qtbot.waitUntil(lambda: scroll.verticalScrollBar().maximum() > 0)
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    scroll_before = scroll.verticalScrollBar().value()
    save.click()
    qtbot.waitUntil(lambda: scroll.verticalScrollBar().value() > scroll_before)

    loaded = harness.repository.load("Quiet Copy")
    assert loaded.warning is None
    assert isinstance(loaded.profile.bindings[BindableGesture.LEFT_WINK], DisabledAction)
    assert source.text() == "Quiet Copy"
    assert active.text() == "Default"
    assert harness.controller.state.source_outdated
    assert feedback.property("feedbackStatus") == "success"
    assert "not activated" in feedback.text()
    assert name.text() == ""


def test_dirty_draft_survives_runtime_change_until_explicit_discard(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _binding_page(qtbot, tmp_path)
    _select_kind(
        _combo(harness.page, BindableGesture.LEFT_WINK),
        EditableActionKind.DISABLED,
    )
    outdated = _required_child(harness.page, QLabel, "warningBanner")
    load_active = _required_child(harness.page, QPushButton, "loadActiveBindingsButton")

    harness.controller.observe_active_profile(disabled_profile("Quiet"))

    assert harness.controller.state.source_outdated
    assert isinstance(
        harness.controller.state.draft_profile.bindings[BindableGesture.LEFT_WINK],
        DisabledAction,
    )
    assert outdated.isHidden() is False
    assert load_active.isEnabled()

    load_active.click()
    reloaded = harness.controller.state

    assert reloaded.source_profile == disabled_profile("Quiet")
    assert not reloaded.source_outdated
    assert not reloaded.dirty


def test_invalid_row_text_survives_external_runtime_profile_change(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _binding_page(qtbot, tmp_path)
    gesture = BindableGesture.LEFT_WINK
    combo = _combo(harness.page, gesture)
    parameters = _parameters(harness.page, gesture)
    _select_kind(combo, EditableActionKind.MOUSE_SCROLL)
    parameters.setText("0")

    harness.controller.observe_active_profile(disabled_profile("Quiet"))

    assert combo.currentData() == EditableActionKind.MOUSE_SCROLL.value
    assert parameters.text() == "0"
    assert harness.controller.state.error_for(gesture) is not None
    assert harness.controller.state.source_outdated


def test_storage_unavailable_disables_only_persistence_controls(
    qtbot: QtBot,
) -> None:
    controller = BindingEditorController(default_profile())
    page = BindingsPage(controller)
    page.setStyleSheet(build_stylesheet())
    qtbot.addWidget(page)
    name = _required_child(page, QLineEdit, "bindingCopyName")
    save = _required_child(page, QPushButton, "saveBindingDraftButton")
    combo = _combo(page, BindableGesture.LEFT_WINK)
    storage_notices = page.findChildren(QLabel, "warningBanner")

    assert not name.isEnabled()
    assert not save.isEnabled()
    assert combo.isEnabled()
    assert any("storage is unavailable" in notice.text() for notice in storage_notices)


def test_bindings_page_has_no_hidden_horizontal_overflow_at_690_px(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    profile_name = "W" * 80
    active = disabled_profile(profile_name)
    repository.create(active)
    controller = BindingEditorController(active, repository=repository)
    page = BindingsPage(controller)
    page.setStyleSheet(build_stylesheet())
    qtbot.addWidget(page)
    scroll = _required_child(page, QScrollArea, "bindingsPageScroll")
    content = _required_child(page, QWidget, "bindingsPageContent")
    page.setFixedSize(690, 640)
    page.show()
    qtbot.waitUntil(lambda: scroll.horizontalScrollBar().maximum() == 0)

    assert scroll.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert content.width() <= scroll.viewport().width()
    assert scroll.horizontalScrollBar().maximum() == 0
    content_right = content.contentsRect().right()
    widgets: tuple[QWidget, ...] = (
        _combo(page, BindableGesture.LEFT_WINK),
        _parameters(page, BindableGesture.LEFT_WINK),
        _required_child(page, QTableWidget, "draftBindingsTable"),
        _required_child(page, QLineEdit, "bindingCopyName"),
        _required_child(page, QPushButton, "saveBindingDraftButton"),
    )
    for widget in widgets:
        mapped_right = widget.mapTo(content, QPoint(widget.width() - 1, 0)).x()
        assert mapped_right <= content_right, widget.objectName()
