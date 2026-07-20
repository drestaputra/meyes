"""Profile catalog and fail-closed runtime activation tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from meyes.bindings.defaults import default_profile, disabled_profile
from meyes.bindings.manager import BindingManager
from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.bindings.repository import BindingProfileRepository
from meyes.bindings.transfer import read_profile_file, write_profile_file
from meyes.domain.actions import DisabledAction, MouseButton, MouseDownAction
from meyes.domain.events import GestureEvent, GestureEventType
from meyes.input.fake import FakeInputExecutor, InputCall
from meyes.services.action_dispatcher import DispatcherSnapshot, DispatcherState, LifecycleReport
from meyes.ui.action_simulation import ActionSimulationController, simulation_input_call
from meyes.ui.profile_controller import (
    ProfileController,
    ProfileOperationResult,
    binding_profile,
    profile_names,
    profile_operation,
)
from meyes.util.paths import AppPaths


@dataclass(slots=True)
class ManualClock:
    value: float = 1.0

    def __call__(self) -> float:
        return self.value


@dataclass(slots=True)
class RecordingPersistence:
    names: list[str] = field(default_factory=list)

    def __call__(self, profile_name: str) -> None:
        self.names.append(profile_name)


@dataclass(slots=True)
class FailingPersistence:
    names: list[str] = field(default_factory=list)

    def __call__(self, profile_name: str) -> None:
        self.names.append(profile_name)
        raise OSError("injected active-profile persistence failure")


class FailOnReleaseAttemptExecutor(FakeInputExecutor):
    """Fail one selected cleanup attempt after recording it."""

    def __init__(self, fail_on_attempt: int) -> None:
        super().__init__()
        self._fail_on_attempt = fail_on_attempt
        self.release_attempts = 0

    def release_all(self) -> None:
        self.release_attempts += 1
        if self.release_attempts == self._fail_on_attempt:
            self.release_all_calls += 1
            self.calls.append(InputCall("release_all"))
            raise RuntimeError("injected rollback release failure")
        super().release_all()


def make_controller(
    tmp_path: Path,
    *,
    active_profile: BindingProfile | None = None,
    repository: BindingProfileRepository | None = None,
    persistence: RecordingPersistence | FailingPersistence | None = None,
    executor: FakeInputExecutor | None = None,
    clock: ManualClock | None = None,
) -> tuple[
    ProfileController,
    ActionSimulationController,
    BindingProfileRepository,
    RecordingPersistence | FailingPersistence,
    FakeInputExecutor,
    ManualClock,
]:
    selected = active_profile or default_profile()
    profile_repository = repository or BindingProfileRepository(AppPaths.under(tmp_path))
    active_persistence = persistence or RecordingPersistence()
    fake = executor or FakeInputExecutor()
    manual_clock = clock or ManualClock()
    simulation = ActionSimulationController(
        BindingManager(selected),
        executor=fake,
        clock=manual_clock,
    )
    controller = ProfileController(
        selected,
        simulation,
        repository=profile_repository,
        persist_active_profile=active_persistence,
    )
    return (
        controller,
        simulation,
        profile_repository,
        active_persistence,
        fake,
        manual_clock,
    )


def held_mouse_profile(profile_name: str) -> BindingProfile:
    bindings = dict(disabled_profile(profile_name).bindings)
    bindings[BindableGesture.LEFT_TEMPLE_HOLD] = MouseDownAction(button=MouseButton.LEFT)
    return BindingProfile(profile_name=profile_name, bindings=bindings)


def hold_start(timestamp: float = 1.0) -> GestureEvent:
    return GestureEvent(
        GestureEventType.LEFT_TEMPLE_HOLD_START,
        timestamp=timestamp,
        source_sequence=1,
        duration_ms=550.0,
    )


def test_create_disabled_normalizes_persists_and_emits_catalog(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    controller, _, repository, persistence, _, _ = make_controller(tmp_path)
    catalog_signals: list[tuple[str, ...]] = []
    operation_signals: list[ProfileOperationResult] = []
    controller.profiles_changed.connect(
        lambda payload: catalog_signals.append(profile_names(payload))
    )
    controller.operation_finished.connect(
        lambda payload: operation_signals.append(profile_operation(payload))
    )

    result = controller.create_disabled("  Work Profile  ")

    assert result.success
    assert result.profile_name == "Work Profile"
    assert controller.profile_names == ("Default", "Work Profile")
    assert catalog_signals == [("Default", "Work Profile")]
    assert operation_signals == [result]
    loaded = repository.load("Work Profile")
    assert loaded.warning is None
    assert loaded.profile.profile_name == "Work Profile"
    assert all(isinstance(action, DisabledAction) for action in loaded.profile.bindings.values())
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


@pytest.mark.parametrize(
    "invalid_name",
    ["", "   ", "../Escape", "bad:name", "CON", "name."],
)
def test_create_disabled_rejects_invalid_names_without_catalog_mutation(
    qtbot: QtBot,
    tmp_path: Path,
    invalid_name: str,
) -> None:
    del qtbot
    controller, _, repository, persistence, _, _ = make_controller(tmp_path)
    catalog_signals: list[tuple[str, ...]] = []
    controller.profiles_changed.connect(
        lambda payload: catalog_signals.append(profile_names(payload))
    )

    result = controller.create_disabled(invalid_name)

    assert not result.success
    assert "1-80" in result.message
    assert result.profile_name is None
    assert controller.profile_names == ("Default",)
    assert repository.list_profile_names() == ("Default",)
    assert catalog_signals == []
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_create_disabled_accepts_80_characters_and_rejects_81(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    controller, _, repository, _, _, _ = make_controller(tmp_path)
    accepted_name = "A" * 80
    rejected_name = "B" * 81

    accepted = controller.create_disabled(accepted_name)
    rejected = controller.create_disabled(rejected_name)

    assert accepted.success
    assert accepted.profile_name == accepted_name
    assert repository.load(accepted_name).warning is None
    assert not rejected.success
    assert "1-80" in rejected.message
    assert rejected_name not in controller.profile_names
    assert controller.profile_names == ("Default", accepted_name)


def test_create_disabled_rejects_case_insensitive_duplicate_without_overwrite(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    controller, _, repository, _, _, _ = make_controller(tmp_path)
    catalog_signals: list[tuple[str, ...]] = []
    controller.profiles_changed.connect(
        lambda payload: catalog_signals.append(profile_names(payload))
    )

    created = controller.create_disabled("Work")
    duplicate = controller.create_disabled("work")

    assert created.success
    assert not duplicate.success
    assert "already exists" in duplicate.message
    assert controller.profile_names == ("Default", "Work")
    assert catalog_signals == [("Default", "Work")]
    loaded = repository.load("Work")
    assert loaded.warning is None
    assert loaded.profile == disabled_profile("Work")


def test_activation_releases_pauses_persists_and_emits_in_order(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    original = held_mouse_profile("Original")
    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    replacement = disabled_profile("Replacement")
    repository.create(original)
    repository.create(replacement)
    persistence = RecordingPersistence()
    controller, simulation, _, _, fake, clock = make_controller(
        tmp_path,
        active_profile=original,
        repository=repository,
        persistence=persistence,
    )
    assert simulation.start().success
    assert simulation.dispatch_event(hold_start(clock.value)) is not None
    assert fake.held_buttons == {MouseButton.LEFT}

    events: list[str] = []

    def record_input(payload: object) -> None:
        events.append(f"input:{simulation_input_call(payload).operation}")

    def record_lifecycle(payload: object) -> None:
        assert isinstance(payload, LifecycleReport)
        events.append(f"lifecycle:{payload.state.value}")

    def record_snapshot(payload: object) -> None:
        assert isinstance(payload, DispatcherSnapshot)
        events.append(f"snapshot:{payload.profile_name}:{payload.state.value}")

    simulation.input_call_emitted.connect(record_input)
    simulation.lifecycle_reported.connect(record_lifecycle)
    simulation.snapshot_changed.connect(record_snapshot)
    simulation.tracking_pause_requested.connect(lambda: events.append("tracking-pause"))
    controller.active_profile_changed.connect(
        lambda payload: events.append(f"active:{binding_profile(payload).profile_name}")
    )
    controller.operation_finished.connect(
        lambda payload: events.append(f"finished:{profile_operation(payload).success}")
    )

    def persist_and_record(profile_name: str) -> None:
        events.append(f"persist:{profile_name}")
        persistence(profile_name)

    controller._persist_active_profile = persist_and_record

    result = controller.activate("Replacement")

    assert result.success
    assert result.profile_name == "Replacement"
    assert controller.active_profile == replacement
    assert simulation.active_profile == replacement
    assert simulation.state is DispatcherState.PAUSED
    assert not simulation.timer_active
    assert fake.held_buttons == set()
    assert persistence.names == ["Replacement"]
    assert simulation.simulated_calls[-3:] == (
        InputCall("mouse_up", (MouseButton.LEFT,)),
        InputCall("release_all"),
        InputCall("release_all"),
    )
    assert events == [
        "input:mouse_up",
        "input:release_all",
        "lifecycle:paused",
        "snapshot:Original:paused",
        "tracking-pause",
        "input:release_all",
        "lifecycle:paused",
        "snapshot:Replacement:paused",
        "persist:Replacement",
        "active:Replacement",
        "finished:True",
    ]


def test_activation_of_current_profile_is_idempotent(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    controller, simulation, _, persistence, fake, _ = make_controller(tmp_path)
    assert simulation.start().success
    calls_before = simulation.simulated_calls
    release_count_before = fake.release_all_calls
    lifecycle_signals: list[LifecycleReport] = []
    active_signals: list[BindingProfile] = []
    pause_requests: list[str] = []
    simulation.lifecycle_reported.connect(lifecycle_signals.append)
    simulation.tracking_pause_requested.connect(lambda: pause_requests.append("pause"))
    controller.active_profile_changed.connect(
        lambda payload: active_signals.append(binding_profile(payload))
    )

    result = controller.activate(" default ")

    assert result.success
    assert result.profile_name == "Default"
    assert simulation.state is DispatcherState.ACTIVE
    assert simulation.simulated_calls == calls_before
    assert fake.release_all_calls == release_count_before
    assert lifecycle_signals == []
    assert pause_requests == []
    assert active_signals == []
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_load_warning_keeps_previous_profile_and_leaves_runtime_paused(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    controller, simulation, repository, persistence, fake, _ = make_controller(tmp_path)
    assert simulation.start().success
    active_signals: list[BindingProfile] = []
    pause_requests: list[str] = []
    controller.active_profile_changed.connect(
        lambda payload: active_signals.append(binding_profile(payload))
    )
    simulation.tracking_pause_requested.connect(lambda: pause_requests.append("pause"))

    result = controller.activate("Missing")

    assert not result.success
    assert "could not be loaded" in result.message
    assert "previous profile remains" in result.message
    assert controller.active_profile == default_profile()
    assert simulation.active_profile == default_profile()
    assert simulation.state is DispatcherState.PAUSED
    assert fake.release_all_calls == 2
    assert pause_requests == ["pause"]
    assert active_signals == []
    assert repository.load("Missing").warning is not None
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_persistence_failure_rolls_back_profile_and_remains_paused(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    original = held_mouse_profile("Original")
    replacement = disabled_profile("Replacement")
    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    repository.create(original)
    repository.create(replacement)
    persistence = FailingPersistence()
    controller, simulation, _, _, fake, clock = make_controller(
        tmp_path,
        active_profile=original,
        repository=repository,
        persistence=persistence,
    )
    assert simulation.start().success
    assert simulation.dispatch_event(hold_start(clock.value)) is not None
    active_signals: list[BindingProfile] = []
    controller.active_profile_changed.connect(
        lambda payload: active_signals.append(binding_profile(payload))
    )

    result = controller.activate("Replacement")

    assert not result.success
    assert "previous profile was restored" in result.message
    assert persistence.names == ["Replacement"]
    assert controller.active_profile == original
    assert simulation.active_profile == original
    assert simulation.state is DispatcherState.PAUSED
    assert not simulation.timer_active
    assert fake.held_buttons == set()
    assert active_signals == []
    assert simulation.simulated_calls[-4:] == (
        InputCall("mouse_up", (MouseButton.LEFT,)),
        InputCall("release_all"),
        InputCall("release_all"),
        InputCall("release_all"),
    )


def test_failed_persistence_and_failed_rollback_reconcile_visible_runtime_profile(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    original = disabled_profile("Original")
    replacement = disabled_profile("Replacement")
    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    repository.create(original)
    repository.create(replacement)
    persistence = FailingPersistence()
    executor = FailOnReleaseAttemptExecutor(fail_on_attempt=4)
    controller, simulation, _, _, _, _ = make_controller(
        tmp_path,
        active_profile=original,
        repository=repository,
        persistence=persistence,
        executor=executor,
    )
    assert simulation.start().success
    active_signals: list[BindingProfile] = []
    controller.active_profile_changed.connect(
        lambda payload: active_signals.append(binding_profile(payload))
    )

    result = controller.activate("Replacement")

    assert not result.success
    assert result.warning
    assert result.profile_name == "Replacement"
    assert "remains loaded in a fail-closed simulator" in result.message
    assert persistence.names == ["Replacement"]
    assert executor.release_attempts == 4
    assert controller.active_profile == replacement
    assert simulation.active_profile == replacement
    assert simulation.state is DispatcherState.FAULTED
    assert active_signals == [replacement]


def test_rename_inactive_profile_preserves_runtime_and_updates_catalog(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    stored = held_mouse_profile("Work")
    repository.create(stored)
    controller, simulation, _, persistence, fake, _ = make_controller(
        tmp_path,
        repository=repository,
    )
    assert simulation.start().success
    calls_before = simulation.simulated_calls
    signals: list[tuple[str, ...]] = []
    controller.profiles_changed.connect(lambda payload: signals.append(profile_names(payload)))

    result = controller.rename("Work", "Focus")

    assert result.success
    assert result.profile_name == "Focus"
    assert controller.profile_names == ("Default", "Focus")
    assert signals == [("Default", "Focus")]
    assert repository.load("Work").warning is not None
    renamed = repository.load("Focus")
    assert renamed.warning is None
    assert renamed.profile.bindings == stored.bindings
    assert controller.active_profile == default_profile()
    assert simulation.active_profile == default_profile()
    assert simulation.state is DispatcherState.ACTIVE
    assert simulation.simulated_calls == calls_before
    assert fake.release_all_calls == 1
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_delete_requires_exact_name_and_retains_recovery_backup(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    repository.create(disabled_profile("Work"))
    controller, simulation, _, persistence, fake, _ = make_controller(
        tmp_path,
        repository=repository,
    )
    calls_before = simulation.simulated_calls
    release_count_before = fake.release_all_calls

    rejected = controller.delete("Work", "work")
    deleted = controller.delete("Work", "Work")

    assert not rejected.success
    assert "exactly" in rejected.message
    assert deleted.success
    assert deleted.profile_name is None
    assert controller.profile_names == ("Default",)
    assert not (paths.profiles_dir / "Work.json").exists()
    backups = tuple(paths.profiles_dir.glob("Work.deleted-*.bak"))
    assert len(backups) == 1
    assert backups[0].is_file()
    assert controller.active_profile == default_profile()
    assert simulation.active_profile == default_profile()
    assert simulation.simulated_calls == calls_before
    assert fake.release_all_calls == release_count_before
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_restore_default_requires_confirmation_and_keeps_profile_inactive(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    repository.create(disabled_profile("Work"))
    controller, simulation, _, persistence, fake, _ = make_controller(
        tmp_path,
        repository=repository,
    )
    calls_before = simulation.simulated_calls
    release_count_before = fake.release_all_calls

    rejected = controller.restore_default("Work", confirmed=False)
    restored = controller.restore_default("Work", confirmed=True)

    assert not rejected.success
    assert "Confirm" in rejected.message
    assert restored.success
    assert restored.profile_name == "Work"
    loaded = repository.load("Work")
    assert loaded.warning is None
    assert loaded.profile.profile_name == "Work"
    assert loaded.profile.bindings == default_profile().bindings
    assert controller.profile_names == ("Default", "Work")
    assert controller.active_profile == default_profile()
    assert simulation.active_profile == default_profile()
    assert simulation.simulated_calls == calls_before
    assert fake.release_all_calls == release_count_before
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


@pytest.mark.parametrize("operation", ["rename", "delete", "restore_default"])
def test_active_and_default_profiles_are_protected_from_lifecycle_changes(
    qtbot: QtBot,
    tmp_path: Path,
    operation: str,
) -> None:
    del qtbot
    active = disabled_profile("Work")
    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    repository.create(active)
    controller, simulation, _, persistence, _, _ = make_controller(
        tmp_path,
        active_profile=active,
        repository=repository,
    )

    if operation == "rename":
        active_result = controller.rename("Work", "Focus")
        default_result = controller.rename("Default", "Focus")
    elif operation == "delete":
        active_result = controller.delete("Work", "Work")
        default_result = controller.delete("Default", "Default")
    else:
        active_result = controller.restore_default("Work", confirmed=True)
        default_result = controller.restore_default("Default", confirmed=True)

    assert not active_result.success
    assert "Activate another profile" in active_result.message
    assert not default_result.success
    assert "immutable" in default_result.message
    assert repository.catalog().names == ("Default", "Work")
    assert controller.active_profile == active
    assert simulation.active_profile == active
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_import_creates_inactive_profile_without_runtime_or_preference_change(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    source = tmp_path / "imported.json"
    imported = held_mouse_profile("Imported")
    write_profile_file(imported, source)
    controller, simulation, repository, persistence, fake, _ = make_controller(tmp_path)
    calls_before = simulation.simulated_calls
    release_count_before = fake.release_all_calls

    result = controller.import_profile_file(source)

    assert result.success
    assert result.profile_name == "Imported"
    assert controller.profile_names == ("Default", "Imported")
    loaded = repository.read("Imported")
    assert loaded == imported
    assert controller.active_profile == default_profile()
    assert simulation.active_profile == default_profile()
    assert simulation.simulated_calls == calls_before
    assert fake.release_all_calls == release_count_before
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_import_collision_requires_explicit_alternative_local_name(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    repository = BindingProfileRepository(AppPaths.under(tmp_path / "local"))
    repository.create(disabled_profile("Work"))
    source = tmp_path / "incoming.json"
    incoming = held_mouse_profile("Work")
    write_profile_file(incoming, source)
    controller, _, _, persistence, _, _ = make_controller(
        tmp_path,
        repository=repository,
    )

    collision = controller.import_profile_file(source)
    renamed = controller.import_profile_file(source, local_name=" Focus ")

    assert not collision.success
    assert "different local name" in collision.message
    assert renamed.success
    assert renamed.profile_name == "Focus"
    assert controller.profile_names == ("Default", "Focus", "Work")
    assert repository.read("Work") == disabled_profile("Work")
    assert repository.read("Focus").bindings == incoming.bindings
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_import_default_requires_local_name_and_invalid_file_writes_nothing(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    default_source = tmp_path / "default.json"
    invalid_source = tmp_path / "invalid.json"
    write_profile_file(default_profile(), default_source)
    invalid_source.write_text("{}", encoding="utf-8")
    controller, _, repository, persistence, _, _ = make_controller(tmp_path)

    default_collision = controller.import_profile_file(default_source)
    imported_default = controller.import_profile_file(
        default_source,
        local_name="Default Copy",
    )
    invalid = controller.import_profile_file(invalid_source)

    assert not default_collision.success
    assert "Default is built in" in default_collision.message
    assert imported_default.success
    assert repository.read("Default Copy").bindings == default_profile().bindings
    assert not invalid.success
    assert "not a valid MEYES profile" in invalid.message
    assert controller.profile_names == ("Default", "Default Copy")
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_import_rejects_non_string_local_name_without_reading_source(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    controller, _, _, persistence, _, _ = make_controller(tmp_path)

    result = controller.import_profile_file(
        tmp_path / "missing.json",
        local_name=object(),
    )

    assert not result.success
    assert "local profile name is invalid" in result.message
    assert controller.profile_names == ("Default",)
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_export_is_read_only_and_requires_explicit_overwrite(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    repository = BindingProfileRepository(AppPaths.under(tmp_path / "local"))
    repository.create(held_mouse_profile("Work"))
    controller, simulation, _, persistence, fake, _ = make_controller(
        tmp_path,
        repository=repository,
    )
    destination = tmp_path / "export.json"
    calls_before = simulation.simulated_calls
    release_count_before = fake.release_all_calls

    exported = controller.export_profile_file("Work", destination)
    collision = controller.export_profile_file("Default", destination)
    overwritten = controller.export_profile_file(
        "Default",
        destination,
        overwrite=True,
    )

    assert exported.success
    assert not collision.success
    assert "already exists" in collision.message
    assert overwritten.success
    assert read_profile_file(destination) == default_profile()
    assert controller.profile_names == ("Default", "Work")
    assert controller.active_profile == default_profile()
    assert simulation.active_profile == default_profile()
    assert simulation.simulated_calls == calls_before
    assert fake.release_all_calls == release_count_before
    assert isinstance(persistence, RecordingPersistence)
    assert persistence.names == []


def test_transfer_operations_fail_closed_when_storage_or_files_are_unavailable(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    del qtbot
    profile = default_profile()
    simulation = ActionSimulationController(BindingManager(profile))
    controller = ProfileController(profile, simulation)

    imported = controller.import_profile_file(tmp_path / "missing.json")
    exported = controller.export_profile_file("Default", tmp_path / "export.json")

    assert not imported.success
    assert "unavailable" in imported.message
    assert not exported.success
    assert "unavailable" in exported.message


def test_profile_signal_payload_validators_accept_expected_values_and_reject_others() -> None:
    result = ProfileOperationResult(True, "done", profile_name="Default")
    names = ("Default", "Work")
    profile = default_profile()

    assert profile_operation(result) is result
    assert profile_names(names) is names
    assert binding_profile(profile) is profile

    with pytest.raises(TypeError, match="Expected ProfileOperationResult"):
        profile_operation(object())
    with pytest.raises(TypeError, match="Expected tuple of profile names"):
        profile_names(["Default"])
    with pytest.raises(TypeError, match="Expected tuple of profile names"):
        profile_names(("Default", 7))
    with pytest.raises(TypeError, match="Expected BindingProfile"):
        binding_profile(object())
