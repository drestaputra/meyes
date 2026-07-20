"""Native profile catalog UI tests with fake-only runtime activation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
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


def _profile_page(qtbot: QtBot, tmp_path: Path) -> ProfilePageHarness:
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
    page = ProfilesPage(controller)
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
    for widget in (profile_list, name_input, create_button, activate_button, preview):
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
