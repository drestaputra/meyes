"""Native profile catalog UI tests with fake-only runtime activation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot

from meyes.bindings.defaults import default_profile, disabled_profile
from meyes.bindings.manager import BindingManager
from meyes.bindings.models import BindableGesture
from meyes.bindings.presentation import action_label, gesture_label
from meyes.bindings.repository import BindingProfileRepository
from meyes.bindings.transfer import read_profile_file, write_profile_file
from meyes.domain.actions import DisabledAction
from meyes.ui.action_simulation import ActionSimulationController
from meyes.ui.profile_controller import ProfileController
from meyes.ui.profiles_page import ProfilesPage
from meyes.ui.theme import build_stylesheet
from meyes.util.paths import AppPaths

WidgetT = TypeVar("WidgetT", bound=QWidget)


@dataclass(slots=True)
class ProfilePageHarness:
    """Keep the Qt owners and persistence collaborators alive for one test."""

    page: ProfilesPage
    controller: ProfileController
    simulation: ActionSimulationController
    repository: BindingProfileRepository
    paths: AppPaths
    persisted_names: list[str]


def _profile_page(
    qtbot: QtBot,
    tmp_path: Path,
    *,
    prepare_transfer: Callable[[], bool] | None = None,
) -> ProfilePageHarness:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    profile = default_profile()
    simulation = ActionSimulationController(BindingManager(profile))
    persisted_names: list[str] = []
    controller = ProfileController(
        profile,
        simulation,
        repository=repository,
        persist_active_profile=persisted_names.append,
    )
    page = ProfilesPage(controller, prepare_transfer=prepare_transfer)
    page.setStyleSheet(build_stylesheet())
    qtbot.addWidget(page)
    return ProfilePageHarness(
        page,
        controller,
        simulation,
        repository,
        paths,
        persisted_names,
    )


def _required_child(parent: QWidget, widget_type: type[WidgetT], name: str) -> WidgetT:
    child = parent.findChild(widget_type, name)
    assert child is not None, f"missing {widget_type.__name__}#{name}"
    return child


def _table_text(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


def _profile_row(profile_list: QListWidget, profile_name: str) -> int:
    for row in range(profile_list.count()):
        item = profile_list.item(row)
        if item.data(Qt.ItemDataRole.UserRole) == profile_name:
            return row
    raise AssertionError(f"profile row not found: {profile_name}")


def test_default_profile_is_marked_active_and_all_six_bindings_are_previewed(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _profile_page(qtbot, tmp_path)
    profile_list = _required_child(harness.page, QListWidget, "profileList")
    preview = _required_child(harness.page, QTableWidget, "activeBindingsTable")
    active_value = _required_child(harness.page, QLabel, "activeProfileValue")
    name_input = _required_child(harness.page, QLineEdit, "newProfileName")
    create_button = _required_child(harness.page, QPushButton, "createProfileButton")
    activate_button = _required_child(harness.page, QPushButton, "activateProfileButton")
    rename_input = _required_child(harness.page, QLineEdit, "renameProfileName")
    rename_button = _required_child(harness.page, QPushButton, "renameProfileButton")
    restore_confirmation = _required_child(
        harness.page,
        QCheckBox,
        "restoreDefaultConfirmation",
    )
    delete_confirmation = _required_child(
        harness.page,
        QLineEdit,
        "deleteProfileConfirmation",
    )
    delete_button = _required_child(harness.page, QPushButton, "deleteProfileButton")
    import_path = _required_child(harness.page, QLineEdit, "importProfilePath")
    import_name = _required_child(harness.page, QLineEdit, "importProfileName")
    browse_import = _required_child(harness.page, QPushButton, "browseImportProfileButton")
    import_button = _required_child(harness.page, QPushButton, "importProfileButton")
    export_button = _required_child(harness.page, QPushButton, "exportProfileButton")
    safety_banner = _required_child(harness.page, QLabel, "safeBanner")

    assert profile_list.count() == 1
    default_item = profile_list.item(0)
    assert default_item.data(Qt.ItemDataRole.UserRole) == "Default"
    assert "Active" in default_item.text()
    assert active_value.text() == "Default"
    assert preview.rowCount() == len(BindableGesture) == 6
    assert preview.columnCount() == 2
    assert _table_text(preview, 0, 0) == "Left wink"
    assert _table_text(preview, 5, 0) == "Right temple hold"
    for row, gesture in enumerate(BindableGesture):
        assert _table_text(preview, row, 0) == gesture_label(gesture)
        assert _table_text(preview, row, 1) == action_label(default_profile().bindings[gesture])

    assert profile_list.accessibleName() == "Local binding profiles"
    assert preview.accessibleName() == "Active gesture bindings"
    assert active_value.accessibleName() == "Active profile"
    assert name_input.accessibleName() == "New profile name"
    assert create_button.accessibleName() == "Create all-disabled profile"
    assert activate_button.accessibleName() == "Use selected profile and pause tracking"
    assert rename_input.accessibleName() == "New name for selected profile"
    assert rename_button.accessibleName() == "Rename selected inactive profile"
    assert restore_confirmation.accessibleName() == "Confirm replacing all bindings with Default"
    assert delete_confirmation.accessibleName() == "Exact selected profile name to confirm deletion"
    assert delete_button.accessibleName() == "Delete selected inactive profile"
    assert import_path.accessibleName() == "Selected profile import file"
    assert import_name.accessibleName() == "Optional local name for imported profile"
    assert browse_import.accessibleName() == "Choose profile JSON to import"
    assert import_button.accessibleName() == "Import selected JSON as inactive profile"
    assert export_button.accessibleName() == "Export selected profile to JSON"
    assert browse_import.isEnabled()
    assert not import_button.isEnabled()
    assert export_button.isEnabled()
    assert "Activation and file dialogs disarm Live Input" in safety_banner.text()
    assert "persistent status bar" in safety_banner.text()


def test_profile_mutation_controls_are_disabled_without_persistence(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    profile = default_profile()
    simulation = ActionSimulationController(BindingManager(profile))
    controller = ProfileController(profile, simulation, repository=repository)
    page = ProfilesPage(controller)
    page.setStyleSheet(build_stylesheet())
    qtbot.addWidget(page)

    name_input = _required_child(page, QLineEdit, "newProfileName")
    create_button = _required_child(page, QPushButton, "createProfileButton")
    activate_button = _required_child(page, QPushButton, "activateProfileButton")
    refresh_button = _required_child(page, QPushButton, "refreshProfilesButton")
    storage_notice = _required_child(page, QLabel, "warningBanner")

    assert controller.can_manage is False
    assert name_input.isEnabled() is False
    assert create_button.isEnabled() is False
    assert activate_button.isEnabled() is False
    assert refresh_button.isEnabled() is True
    assert storage_notice.isHidden() is False
    assert "unavailable" in storage_notice.text().lower()
    assert not list(paths.profiles_dir.glob("*.json"))


def test_missing_active_profile_is_disclosed_as_a_recovery_snapshot(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    recovered = repository.load("Missing").profile
    simulation = ActionSimulationController(BindingManager(recovered))
    controller = ProfileController(
        recovered,
        simulation,
        repository=repository,
        persist_active_profile=lambda _name: None,
    )
    page = ProfilesPage(controller)
    page.setStyleSheet(build_stylesheet())
    qtbot.addWidget(page)
    profile_list = _required_child(page, QListWidget, "profileList")
    feedback = _required_child(page, QLabel, "profileFeedback")
    active_value = _required_child(page, QLabel, "activeProfileValue")
    preview = _required_child(page, QTableWidget, "activeBindingsTable")

    assert controller.profile_names == ("Default",)
    assert profile_list.count() == 1
    assert profile_list.item(0).data(Qt.ItemDataRole.UserRole) == "Default"
    assert "Active" not in profile_list.item(0).text()
    assert active_value.text() == "Missing"
    assert feedback.property("feedbackStatus") == "warning"
    assert "recovery snapshot" in feedback.text()
    assert [_table_text(preview, row, 1) for row in range(6)] == ["Disabled"] * 6


def test_invalid_catalog_file_warning_is_rendered_inline(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    (paths.profiles_dir / "Broken.json").write_text("{}", encoding="utf-8")
    repository = BindingProfileRepository(paths)
    profile = default_profile()
    simulation = ActionSimulationController(BindingManager(profile))
    controller = ProfileController(
        profile,
        simulation,
        repository=repository,
        persist_active_profile=lambda _name: None,
    )
    page = ProfilesPage(controller)
    page.setStyleSheet(build_stylesheet())
    qtbot.addWidget(page)
    feedback = _required_child(page, QLabel, "profileFeedback")

    assert feedback.property("feedbackStatus") == "warning"
    assert "ignored" in feedback.text()


def test_valid_profile_creation_persists_and_selects_without_activating(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _profile_page(qtbot, tmp_path)
    profile_list = _required_child(harness.page, QListWidget, "profileList")
    name_input = _required_child(harness.page, QLineEdit, "newProfileName")
    create_button = _required_child(harness.page, QPushButton, "createProfileButton")
    activate_button = _required_child(harness.page, QPushButton, "activateProfileButton")
    feedback = _required_child(harness.page, QLabel, "profileFeedback")

    name_input.setText("Work")
    assert create_button.isEnabled() is True
    create_button.click()

    assert profile_list.count() == 2
    assert profile_list.currentItem().data(Qt.ItemDataRole.UserRole) == "Work"
    assert "Active" not in profile_list.currentItem().text()
    assert activate_button.isEnabled() is True
    assert harness.controller.active_profile.profile_name == "Default"
    assert harness.persisted_names == []
    assert feedback.property("feedbackStatus") == "success"
    assert "Created" in feedback.text()
    assert (harness.paths.profiles_dir / "Work.json").is_file()
    loaded = harness.repository.load("Work")
    assert loaded.warning is None
    assert all(isinstance(action, DisabledAction) for action in loaded.profile.bindings.values())


def test_invalid_profile_name_shows_inline_error_and_writes_nothing(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _profile_page(qtbot, tmp_path)
    profile_list = _required_child(harness.page, QListWidget, "profileList")
    name_input = _required_child(harness.page, QLineEdit, "newProfileName")
    create_button = _required_child(harness.page, QPushButton, "createProfileButton")
    feedback = _required_child(harness.page, QLabel, "profileFeedback")

    name_input.setText("CON")
    create_button.click()

    assert profile_list.count() == 1
    assert harness.controller.profile_names == ("Default",)
    assert feedback.isHidden() is False
    assert feedback.property("feedbackStatus") == "error"
    assert "Windows-reserved" in feedback.text()
    assert not list(harness.paths.profiles_dir.glob("*.json"))


def test_activating_created_profile_updates_active_marker_and_binding_preview(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _profile_page(qtbot, tmp_path)
    profile_list = _required_child(harness.page, QListWidget, "profileList")
    name_input = _required_child(harness.page, QLineEdit, "newProfileName")
    create_button = _required_child(harness.page, QPushButton, "createProfileButton")
    activate_button = _required_child(harness.page, QPushButton, "activateProfileButton")
    active_value = _required_child(harness.page, QLabel, "activeProfileValue")
    preview = _required_child(harness.page, QTableWidget, "activeBindingsTable")

    assert _table_text(preview, 0, 1) != "Disabled"
    name_input.setText("Work")
    create_button.click()
    activate_button.click()

    assert harness.controller.active_profile.profile_name == "Work"
    assert harness.simulation.active_profile.profile_name == "Work"
    assert harness.persisted_names == ["Work"]
    assert active_value.text() == "Work"
    assert "Active" in profile_list.item(_profile_row(profile_list, "Work")).text()
    assert "Active" not in profile_list.item(_profile_row(profile_list, "Default")).text()
    assert [_table_text(preview, row, 1) for row in range(preview.rowCount())] == ["Disabled"] * 6
    assert activate_button.isEnabled() is False


def test_lifecycle_controls_protect_default_and_active_profiles(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _profile_page(qtbot, tmp_path)
    page = harness.page
    profile_list = _required_child(page, QListWidget, "profileList")
    name_input = _required_child(page, QLineEdit, "newProfileName")
    create_button = _required_child(page, QPushButton, "createProfileButton")
    activate_button = _required_child(page, QPushButton, "activateProfileButton")
    rename_input = _required_child(page, QLineEdit, "renameProfileName")
    rename_button = _required_child(page, QPushButton, "renameProfileButton")
    restore_confirmation = _required_child(page, QCheckBox, "restoreDefaultConfirmation")
    restore_button = _required_child(page, QPushButton, "restoreDefaultButton")
    delete_confirmation = _required_child(page, QLineEdit, "deleteProfileConfirmation")
    delete_button = _required_child(page, QPushButton, "deleteProfileButton")
    status = _required_child(page, QLabel, "selectedProfileLifecycleStatus")

    assert profile_list.currentItem().data(Qt.ItemDataRole.UserRole) == "Default"
    assert "built in" in status.text()
    assert not rename_input.isEnabled()
    assert not rename_button.isEnabled()
    assert not restore_confirmation.isEnabled()
    assert not restore_button.isEnabled()
    assert not delete_confirmation.isEnabled()
    assert not delete_button.isEnabled()

    name_input.setText("Work")
    create_button.click()
    assert rename_input.isEnabled()
    assert restore_confirmation.isEnabled()
    assert delete_confirmation.isEnabled()
    assert "inactive" in status.text()

    activate_button.click()
    assert harness.controller.active_profile.profile_name == "Work"
    assert "active and protected" in status.text()
    assert not rename_input.isEnabled()
    assert not restore_confirmation.isEnabled()
    assert not delete_confirmation.isEnabled()


def test_ui_rename_restore_and_exact_confirmation_delete_stay_inactive(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _profile_page(qtbot, tmp_path)
    page = harness.page
    profile_list = _required_child(page, QListWidget, "profileList")
    name_input = _required_child(page, QLineEdit, "newProfileName")
    create_button = _required_child(page, QPushButton, "createProfileButton")
    rename_input = _required_child(page, QLineEdit, "renameProfileName")
    rename_button = _required_child(page, QPushButton, "renameProfileButton")
    restore_confirmation = _required_child(page, QCheckBox, "restoreDefaultConfirmation")
    restore_button = _required_child(page, QPushButton, "restoreDefaultButton")
    delete_confirmation = _required_child(page, QLineEdit, "deleteProfileConfirmation")
    delete_button = _required_child(page, QPushButton, "deleteProfileButton")
    feedback = _required_child(page, QLabel, "profileFeedback")

    name_input.setText("Work")
    create_button.click()
    rename_input.setText("Focus")
    assert rename_button.isEnabled()
    rename_button.click()

    assert harness.controller.profile_names == ("Default", "Focus")
    assert profile_list.currentItem().data(Qt.ItemDataRole.UserRole) == "Focus"
    assert not (harness.paths.profiles_dir / "Work.json").exists()
    assert (harness.paths.profiles_dir / "Focus.json").is_file()
    assert harness.controller.active_profile == default_profile()
    assert harness.persisted_names == []
    assert "Renamed" in feedback.text()

    restore_confirmation.setChecked(True)
    assert restore_button.isEnabled()
    restore_button.click()
    restored = harness.repository.load("Focus")
    assert restored.warning is None
    assert restored.profile.bindings == default_profile().bindings
    assert harness.controller.active_profile == default_profile()
    assert "Restored" in feedback.text()

    delete_confirmation.setText("focus")
    assert not delete_button.isEnabled()
    delete_confirmation.setText("Focus")
    assert delete_button.isEnabled()
    delete_button.click()

    assert list(harness.controller.profile_names) == ["Default"]
    current_item = profile_list.currentItem()
    assert current_item is not None
    assert current_item.data(Qt.ItemDataRole.UserRole) == "Default"
    assert not (harness.paths.profiles_dir / "Focus.json").exists()
    assert len(tuple(harness.paths.profiles_dir.glob("Focus.deleted-*.bak"))) == 1
    assert harness.controller.active_profile == default_profile()
    assert harness.simulation.active_profile == default_profile()
    assert harness.persisted_names == []
    assert "recovery backup" in feedback.text()


def test_import_dialog_creates_inactive_profile_without_runtime_activation(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "outside" / "imported.json"
    source.parent.mkdir()
    imported = disabled_profile("Imported")
    write_profile_file(imported, source)
    prepare_calls: list[str] = []

    def prepare_transfer() -> bool:
        prepare_calls.append("prepare")
        return True

    harness = _profile_page(
        qtbot,
        tmp_path / "local",
        prepare_transfer=prepare_transfer,
    )
    page = harness.page
    profile_list = _required_child(page, QListWidget, "profileList")
    path_display = _required_child(page, QLineEdit, "importProfilePath")
    browse = _required_child(page, QPushButton, "browseImportProfileButton")
    import_button = _required_child(page, QPushButton, "importProfileButton")
    feedback = _required_child(page, QLabel, "profileFeedback")
    snapshot_before = harness.simulation.snapshot
    calls_before = harness.simulation.simulated_calls
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(source), "MEYES profile (*.json)")),
    )

    browse.click()

    assert prepare_calls == ["prepare"]
    assert path_display.text() == source.name
    assert path_display.toolTip() == str(source)
    assert import_button.isEnabled()

    import_button.click()

    assert harness.controller.profile_names == ("Default", "Imported")
    assert harness.repository.read("Imported") == imported
    assert profile_list.currentItem().data(Qt.ItemDataRole.UserRole) == "Imported"
    assert "Active" not in profile_list.currentItem().text()
    assert harness.controller.active_profile == default_profile()
    assert harness.simulation.snapshot == snapshot_before
    assert harness.simulation.simulated_calls == calls_before
    assert harness.persisted_names == []
    assert path_display.text() == ""
    assert not import_button.isEnabled()
    assert feedback.property("feedbackStatus") == "success"
    assert "inactive" in feedback.text()


def test_export_dialog_writes_selected_snapshot_without_runtime_change(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "outside" / "work.json"
    destination.parent.mkdir()
    prepare_calls: list[str] = []

    def prepare_transfer() -> bool:
        prepare_calls.append("prepare")
        return True

    harness = _profile_page(
        qtbot,
        tmp_path / "local",
        prepare_transfer=prepare_transfer,
    )
    created = harness.controller.create_disabled("Work")
    assert created.success
    page = harness.page
    export_button = _required_child(page, QPushButton, "exportProfileButton")
    feedback = _required_child(page, QLabel, "profileFeedback")
    snapshot_before = harness.simulation.snapshot
    calls_before = harness.simulation.simulated_calls
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *_args, **_kwargs: (str(destination), "MEYES profile (*.json)")),
    )

    export_button.click()

    assert prepare_calls == ["prepare"]
    assert read_profile_file(destination) == disabled_profile("Work")
    assert harness.controller.active_profile == default_profile()
    assert harness.simulation.snapshot == snapshot_before
    assert harness.simulation.simulated_calls == calls_before
    assert harness.persisted_names == []
    assert feedback.property("feedbackStatus") == "success"
    assert "Exported" in feedback.text()


def test_transfer_dialogs_are_blocked_when_live_release_preparation_fails(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _profile_page(qtbot, tmp_path, prepare_transfer=lambda: False)
    page = harness.page
    browse = _required_child(page, QPushButton, "browseImportProfileButton")
    export_button = _required_child(page, QPushButton, "exportProfileButton")
    feedback = _required_child(page, QLabel, "profileFeedback")
    dialog_calls: list[str] = []

    def record_open(*args: object, **kwargs: object) -> tuple[str, str]:
        del args, kwargs
        dialog_calls.append("open")
        return "", ""

    def record_save(*args: object, **kwargs: object) -> tuple[str, str]:
        del args, kwargs
        dialog_calls.append("save")
        return "", ""

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(record_open),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(record_save),
    )

    browse.click()
    export_button.click()

    assert dialog_calls == []
    assert feedback.property("feedbackStatus") == "error"
    assert "could not be released safely" in feedback.text()
    assert harness.controller.profile_names == ("Default",)
    assert harness.persisted_names == []


def test_lifecycle_feedback_scrolls_into_view_after_bottom_action(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _profile_page(qtbot, tmp_path)
    page = harness.page
    scroll = _required_child(page, QScrollArea, "profilesPageScroll")
    name_input = _required_child(page, QLineEdit, "newProfileName")
    create_button = _required_child(page, QPushButton, "createProfileButton")
    delete_confirmation = _required_child(page, QLineEdit, "deleteProfileConfirmation")
    delete_button = _required_child(page, QPushButton, "deleteProfileButton")
    feedback = _required_child(page, QLabel, "profileFeedback")
    page.setFixedSize(690, 640)
    page.show()

    name_input.setText("Work")
    create_button.click()
    delete_confirmation.setText("Work")
    scroll.ensureWidgetVisible(delete_button, 12, 12)
    assert scroll.verticalScrollBar().value() > 0

    delete_button.click()

    def feedback_is_visible() -> bool:
        top = feedback.mapTo(scroll.viewport(), QPoint(0, 0)).y()
        bottom = top + feedback.height()
        return top >= 0 and bottom <= scroll.viewport().height()

    qtbot.waitUntil(feedback_is_visible)
    assert "recovery backup" in feedback.text()


def test_profiles_page_has_no_hidden_horizontal_overflow_at_690_px(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    harness = _profile_page(qtbot, tmp_path)
    page = harness.page
    scroll = _required_child(page, QScrollArea, "profilesPageScroll")
    content = _required_child(page, QWidget, "profilesPageContent")
    profile_list = _required_child(page, QListWidget, "profileList")
    name_input = _required_child(page, QLineEdit, "newProfileName")
    create_button = _required_child(page, QPushButton, "createProfileButton")
    activate_button = _required_child(page, QPushButton, "activateProfileButton")
    rename_input = _required_child(page, QLineEdit, "renameProfileName")
    rename_button = _required_child(page, QPushButton, "renameProfileButton")
    restore_button = _required_child(page, QPushButton, "restoreDefaultButton")
    delete_confirmation = _required_child(page, QLineEdit, "deleteProfileConfirmation")
    delete_button = _required_child(page, QPushButton, "deleteProfileButton")
    import_path = _required_child(page, QLineEdit, "importProfilePath")
    import_name = _required_child(page, QLineEdit, "importProfileName")
    browse_import = _required_child(page, QPushButton, "browseImportProfileButton")
    import_button = _required_child(page, QPushButton, "importProfileButton")
    export_button = _required_child(page, QPushButton, "exportProfileButton")
    preview = _required_child(page, QTableWidget, "activeBindingsTable")

    page.setFixedSize(690, 640)
    page.show()
    qtbot.waitUntil(lambda: content.width() <= scroll.viewport().width())
    qtbot.waitUntil(lambda: scroll.horizontalScrollBar().maximum() == 0)

    assert scroll.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.minimumSizeHint().width() <= page.width()
    assert content.width() <= scroll.viewport().width()
    assert scroll.horizontalScrollBar().maximum() == 0
    content_right = content.contentsRect().right()
    for widget in (
        profile_list,
        name_input,
        create_button,
        activate_button,
        rename_input,
        rename_button,
        restore_button,
        delete_confirmation,
        delete_button,
        import_path,
        import_name,
        browse_import,
        import_button,
        export_button,
        preview,
    ):
        mapped_right = widget.mapTo(content, QPoint(widget.width() - 1, 0)).x()
        assert mapped_right <= content_right, widget.objectName()


def test_maximum_length_profile_name_does_not_expand_profiles_page(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    profile_name = "W" * 80
    active = disabled_profile(profile_name)
    repository.create(active)
    simulation = ActionSimulationController(BindingManager(active))
    controller = ProfileController(
        active,
        simulation,
        repository=repository,
        persist_active_profile=lambda _name: None,
    )
    page = ProfilesPage(controller)
    page.setStyleSheet(build_stylesheet())
    page.setFixedSize(690, 640)
    page.show()
    qtbot.addWidget(page)
    scroll = _required_child(page, QScrollArea, "profilesPageScroll")
    profile_list = _required_child(page, QListWidget, "profileList")
    active_value = _required_child(page, QLabel, "activeProfileValue")
    qtbot.waitUntil(lambda: scroll.horizontalScrollBar().maximum() == 0)

    active_item = profile_list.item(_profile_row(profile_list, profile_name))
    assert "…" in active_item.text()
    assert active_item.toolTip() == profile_name
    assert "…" in active_value.text()
    assert active_value.toolTip() == profile_name
    assert scroll.horizontalScrollBar().maximum() == 0
