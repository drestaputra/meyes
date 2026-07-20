"""Isolated binding draft controller and save-as-copy tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from meyes.bindings.defaults import default_profile, disabled_profile
from meyes.bindings.editor import EditableActionKind
from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.bindings.repository import BindingProfileRepository
from meyes.domain.actions import (
    DisabledAction,
    KeyboardKeyAction,
    KeyName,
    MouseButton,
    MouseClickAction,
)
from meyes.ui.binding_editor_controller import (
    BindingDraftState,
    BindingEditorController,
    BindingSaveResult,
    binding_draft_state,
    binding_profile,
    binding_save_result,
)
from meyes.util.paths import AppPaths


def test_initial_draft_is_an_isolated_clean_active_snapshot(qtbot: QtBot) -> None:
    del qtbot
    active = default_profile()
    controller = BindingEditorController(active)

    state = controller.state

    assert state.source_profile == active
    assert state.draft_profile == active
    assert state.active_profile_name == "Default"
    assert not state.dirty
    assert not state.source_outdated
    assert not state.storage_available
    assert not state.can_save
    assert state.errors == ()


def test_valid_edit_updates_only_the_draft_and_can_be_reset(qtbot: QtBot) -> None:
    del qtbot
    active = default_profile()
    controller = BindingEditorController(active)
    states: list[BindingDraftState] = []
    controller.state_changed.connect(lambda payload: states.append(binding_draft_state(payload)))

    edited = controller.edit_binding(
        BindableGesture.LEFT_WINK,
        EditableActionKind.KEYBOARD_KEY,
        " enter ",
    )

    assert edited.success
    assert controller.state.dirty
    assert controller.state.source_profile == active
    assert controller.state.draft_profile.bindings[BindableGesture.LEFT_WINK] == (
        KeyboardKeyAction(key=KeyName.ENTER)
    )
    assert active.bindings[BindableGesture.LEFT_WINK] == MouseClickAction(button=MouseButton.LEFT)

    reset = controller.reset_binding(BindableGesture.LEFT_WINK)
    reset_state = controller.state

    assert reset.success
    assert not reset_state.dirty
    assert len(states) == 2


def test_invalid_edit_sets_inline_error_without_mutating_last_valid_binding(
    qtbot: QtBot,
) -> None:
    del qtbot
    active = default_profile()
    controller = BindingEditorController(active)

    result = controller.edit_binding(
        BindableGesture.LEFT_WINK,
        EditableActionKind.MOUSE_SCROLL,
        "0",
    )

    state = controller.state
    assert not result.success
    assert state.dirty
    assert state.error_for(BindableGesture.LEFT_WINK) == result.message
    assert (
        state.draft_profile.bindings[BindableGesture.LEFT_WINK]
        == (active.bindings[BindableGesture.LEFT_WINK])
    )
    assert not state.can_save

    controller.reset_all()

    assert controller.state.errors == ()
    assert not controller.state.dirty


def test_clean_draft_rebases_when_active_profile_changes(qtbot: QtBot) -> None:
    del qtbot
    controller = BindingEditorController(default_profile())
    replacement = disabled_profile("Quiet")

    controller.observe_active_profile(replacement)

    assert controller.state.source_profile == replacement
    assert controller.state.draft_profile == replacement
    assert controller.state.active_profile_name == "Quiet"
    assert not controller.state.source_outdated
    assert not controller.state.dirty


def test_dirty_draft_is_preserved_and_marked_outdated_when_active_changes(
    qtbot: QtBot,
) -> None:
    del qtbot
    controller = BindingEditorController(default_profile())
    controller.edit_binding(
        BindableGesture.LEFT_WINK,
        EditableActionKind.DISABLED,
        "",
    )
    draft_before = controller.state.draft_profile

    controller.observe_active_profile(disabled_profile("Quiet"))

    assert controller.state.draft_profile == draft_before
    assert controller.state.source_profile.profile_name == "Default"
    assert controller.state.active_profile_name == "Quiet"
    assert controller.state.source_outdated
    assert controller.state.dirty

    controller.load_active()

    assert controller.state.source_profile == disabled_profile("Quiet")
    assert controller.state.draft_profile == disabled_profile("Quiet")
    assert not controller.state.dirty


def test_save_as_copy_persists_complete_draft_without_activating_source(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    controller = BindingEditorController(default_profile(), repository=repository)
    controller.edit_binding(
        BindableGesture.LEFT_WINK,
        EditableActionKind.DISABLED,
        "",
    )
    saved_signals: list[BindingProfile] = []
    operation_signals: list[BindingSaveResult] = []
    controller.profile_saved.connect(lambda payload: saved_signals.append(binding_profile(payload)))
    controller.operation_finished.connect(
        lambda payload: operation_signals.append(binding_save_result(payload))
    )

    result = controller.save_as_copy("  Quiet Copy  ")

    assert result.success
    assert result.profile_name == "Quiet Copy"
    assert "not activated" in result.message
    loaded = repository.load("Quiet Copy")
    assert loaded.warning is None
    assert isinstance(loaded.profile.bindings[BindableGesture.LEFT_WINK], DisabledAction)
    assert controller.state.source_profile == loaded.profile
    assert controller.state.draft_profile == loaded.profile
    assert controller.state.active_profile_name == "Default"
    assert controller.state.source_outdated
    assert not controller.state.dirty
    assert saved_signals == [loaded.profile]
    assert operation_signals == [result]


def test_save_as_copy_rejects_invalid_duplicate_and_default_names(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    repository.create(disabled_profile("Existing"))
    controller = BindingEditorController(default_profile(), repository=repository)

    invalid = controller.save_as_copy("CON")
    built_in = controller.save_as_copy("default")
    duplicate = controller.save_as_copy("existing")

    assert not invalid.success and "Windows-reserved" in invalid.message
    assert not built_in.success and "built in" in built_in.message
    assert not duplicate.success and "already exists" in duplicate.message
    assert controller.state.source_profile == default_profile()
    assert repository.catalog().names == ("Default", "Existing")


def test_save_is_blocked_by_validation_errors_or_unavailable_storage(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    unavailable = BindingEditorController(default_profile())
    assert not unavailable.save_as_copy("Copy").success

    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    controller = BindingEditorController(default_profile(), repository=repository)
    controller.edit_binding(
        BindableGesture.LEFT_WINK,
        EditableActionKind.MOUSE_CLICK,
        "invalid",
    )

    blocked = controller.save_as_copy("Copy")

    assert not blocked.success
    assert "inline binding error" in blocked.message
    assert repository.catalog().names == ("Default",)


def test_storage_failure_is_sanitized_and_preserves_draft(qtbot: QtBot, tmp_path: Path) -> None:
    del qtbot
    paths = AppPaths.under(tmp_path)
    paths.config_dir.write_text("not a directory", encoding="utf-8")
    controller = BindingEditorController(
        default_profile(),
        repository=BindingProfileRepository(paths),
    )

    result = controller.save_as_copy("Copy")

    assert not result.success
    assert "could not be saved" in result.message
    assert controller.state.source_profile == default_profile()


def test_signal_payload_validators_reject_unexpected_objects() -> None:
    state = BindingEditorController(default_profile()).state
    result = BindingSaveResult(True, "done", profile_name="Copy")
    profile = default_profile()

    assert binding_draft_state(state) is state
    assert binding_save_result(result) is result
    assert binding_profile(profile) is profile

    with pytest.raises(TypeError, match="Expected BindingDraftState"):
        binding_draft_state(object())
    with pytest.raises(TypeError, match="Expected BindingSaveResult"):
        binding_save_result(object())
    with pytest.raises(TypeError, match="Expected BindingProfile"):
        binding_profile(object())
