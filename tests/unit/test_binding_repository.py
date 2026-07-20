"""Atomic, Windows-safe, fail-closed binding profile persistence tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from meyes.bindings.defaults import default_profile, disabled_profile
from meyes.bindings.repository import BindingProfileRepository
from meyes.domain.actions import DisabledAction
from meyes.util.paths import AppPaths


def test_default_profile_is_built_in_and_not_written(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)

    result = repository.load("default")

    assert result.profile == default_profile()
    assert result.warning is None
    assert not paths.profiles_dir.exists()


def test_user_profile_round_trip_is_atomic_and_listed(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    profile = disabled_profile("Work Profile")

    path = repository.save(profile)
    loaded = repository.load("Work Profile")

    assert path == paths.profiles_dir / "Work Profile.json"
    assert loaded.profile == profile
    assert loaded.warning is None
    assert repository.list_profile_names() == ("Default", "Work Profile")
    assert not path.with_suffix(".json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["profile_name"] == "Work Profile"


def test_catalog_returns_canonical_names_without_warning(tmp_path: Path) -> None:
    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    repository.create(disabled_profile("Zulu"))
    repository.create(disabled_profile("alpha"))

    catalog = repository.catalog()

    assert catalog.names == ("Default", "alpha", "Zulu")
    assert catalog.warning is None


def test_create_rejects_case_insensitive_collision_without_overwriting(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    existing = repository.create(disabled_profile("Work"))
    original = existing.read_bytes()

    with pytest.raises(FileExistsError, match="already exists"):
        repository.create(disabled_profile("work"))

    assert existing.read_bytes() == original
    assert repository.catalog().names == ("Default", "Work")
    assert tuple(path.name for path in paths.profiles_dir.glob("*.json")) == ("Work.json",)


def test_create_exclusively_rejects_a_collision_after_the_catalog_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    existing = repository.create(disabled_profile("Work"))
    original = existing.read_bytes()
    monkeypatch.setattr(repository, "_find_profile_path", lambda _name: None)

    with pytest.raises(FileExistsError, match="already exists"):
        repository.create(disabled_profile("Work"))

    assert existing.read_bytes() == original


def test_profile_load_is_case_insensitive_without_quarantining_valid_data(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    path = repository.save(disabled_profile("Work"))

    result = repository.load("work")

    assert result.profile.profile_name == "Work"
    assert result.warning is None
    assert result.recovered_from is None
    assert path.exists()


def test_case_insensitive_filename_is_still_listed_with_profile_casing(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    original = repository.save(disabled_profile("Work"))
    intermediate = paths.profiles_dir / "rename.tmp"
    lowercase = paths.profiles_dir / "work.json"
    original.replace(intermediate)
    intermediate.replace(lowercase)

    assert repository.list_profile_names() == ("Default", "Work")


def test_built_in_default_cannot_be_overwritten(tmp_path: Path) -> None:
    repository = BindingProfileRepository(AppPaths.under(tmp_path))

    with pytest.raises(ValueError, match="immutable"):
        repository.save(default_profile())


def test_repository_revalidates_a_mutated_profile_before_writing(tmp_path: Path) -> None:
    repository = BindingProfileRepository(AppPaths.under(tmp_path))
    profile = disabled_profile("Mutated")
    object.__setattr__(profile, "bindings", {})

    with pytest.raises(ValidationError, match="exactly six"):
        repository.save(profile)


def test_missing_user_profile_fails_closed_without_creating_it(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)

    result = repository.load("Missing")

    assert result.warning is not None
    assert all(isinstance(action, DisabledAction) for action in result.profile.bindings.values())
    assert not (paths.profiles_dir / "Missing.json").exists()


def test_corrupt_profile_is_quarantined_and_fails_closed(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    path = paths.profiles_dir / "Broken.json"
    path.write_text("{not-json", encoding="utf-8")
    fixed_now = datetime(2026, 7, 19, 23, 45, tzinfo=UTC)
    repository = BindingProfileRepository(paths, clock=lambda: fixed_now)

    result = repository.load("Broken")

    assert result.warning is not None
    assert result.recovered_from == paths.profiles_dir / "Broken.invalid-20260719-234500-000000.bak"
    assert result.recovered_from.read_text(encoding="utf-8") == "{not-json"
    assert all(isinstance(action, DisabledAction) for action in result.profile.bindings.values())
    assert not path.exists()


def test_duplicate_json_keys_are_rejected_before_validation(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    path = paths.profiles_dir / "Duplicate.json"
    path.write_text(
        '{"schema_version":1,"schema_version":1,"profile_name":"Duplicate","bindings":{}}',
        encoding="utf-8",
    )
    repository = BindingProfileRepository(paths)

    result = repository.load("Duplicate")

    assert result.warning is not None
    assert "duplicate JSON key" in result.warning
    assert result.recovered_from is not None


def test_profile_name_must_match_filename(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    path = repository.save(disabled_profile("Actual"))
    mismatched = paths.profiles_dir / "Requested.json"
    path.replace(mismatched)

    result = repository.load("Requested")

    assert result.warning is not None
    assert "filename" in result.warning
    assert all(isinstance(action, DisabledAction) for action in result.profile.bindings.values())


@pytest.mark.parametrize("profile_name", ["../outside", "folder/name", "CON", "name."])
def test_repository_fails_closed_for_unsafe_names_before_path_access(
    tmp_path: Path,
    profile_name: str,
) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)

    result = repository.load(profile_name)

    assert result.warning is not None
    assert result.profile.profile_name == "Invalid Profile"
    assert all(isinstance(action, DisabledAction) for action in result.profile.bindings.values())
    assert not paths.config_dir.exists()


def test_listing_ignores_invalid_files_without_mutating_them(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    repository = BindingProfileRepository(paths)
    repository.save(disabled_profile("Valid"))
    invalid = paths.profiles_dir / "Invalid.json"
    invalid.write_text("{}", encoding="utf-8")

    catalog = repository.catalog()

    assert catalog.names == ("Default", "Valid")
    assert catalog.warning is not None
    assert "ignored" in catalog.warning
    assert repository.list_profile_names() == catalog.names
    assert invalid.exists()


def test_unavailable_profile_storage_fails_closed_for_load_and_list(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.config_dir.write_text("not-a-directory", encoding="utf-8")
    repository = BindingProfileRepository(paths)

    result = repository.load("Unavailable")

    assert result.warning is not None
    assert "unavailable" in result.warning
    assert all(isinstance(action, DisabledAction) for action in result.profile.bindings.values())
    catalog = repository.catalog()
    assert catalog.names == ("Default",)
    assert catalog.warning is not None
    assert "could not be read" in catalog.warning
    assert repository.list_profile_names() == catalog.names


def test_secure_temp_write_does_not_follow_a_precreated_legacy_symlink(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    sentinel = tmp_path / "outside.txt"
    sentinel.write_text("keep", encoding="utf-8")
    legacy_temp = paths.profiles_dir / "User.json.tmp"
    _symlink_or_skip(legacy_temp, sentinel)
    repository = BindingProfileRepository(paths)

    saved = repository.save(disabled_profile("User"))

    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert legacy_temp.is_symlink()
    assert saved.is_file()
    assert not saved.is_symlink()


def test_save_rejects_a_symlink_destination_without_touching_target(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    sentinel = tmp_path / "outside.txt"
    sentinel.write_text("keep", encoding="utf-8")
    destination = paths.profiles_dir / "User.json"
    _symlink_or_skip(destination, sentinel)
    repository = BindingProfileRepository(paths)

    with pytest.raises(OSError, match="symlink or reparse"):
        repository.save(disabled_profile("User"))

    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert destination.is_symlink()


def test_profile_directory_symlink_is_not_followed(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.config_dir.mkdir(parents=True)
    outside = tmp_path / "outside-profiles"
    outside.mkdir()
    _symlink_or_skip(paths.profiles_dir, outside, target_is_directory=True)
    repository = BindingProfileRepository(paths)

    result = repository.load("User")

    assert result.warning is not None
    assert all(isinstance(action, DisabledAction) for action in result.profile.bindings.values())
    with pytest.raises(OSError, match="profile directory"):
        repository.save(disabled_profile("User"))
    assert list(outside.iterdir()) == []


def _symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
