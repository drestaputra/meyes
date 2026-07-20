"""Bounded and fail-closed external profile transfer tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from meyes.bindings.defaults import default_profile, disabled_profile
from meyes.bindings.transfer import (
    MAX_PROFILE_FILE_BYTES,
    DuplicateProfileKeyError,
    read_profile_file,
    write_profile_file,
)


def test_profile_file_round_trip_preserves_complete_snapshot(tmp_path: Path) -> None:
    profile = disabled_profile("Quiet Work")
    destination = tmp_path / "quiet-work.json"

    written = write_profile_file(profile, destination)
    loaded = read_profile_file(written)

    assert written == destination
    assert loaded == profile
    assert destination.read_bytes().endswith(b"\n")
    assert json.loads(destination.read_text(encoding="utf-8"))["profile_name"] == "Quiet Work"


def test_profile_import_rejects_duplicate_keys(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.json"
    valid = default_profile().model_dump_json()
    source.write_text(valid.replace("{", '{"profile_name":"Shadow",', 1), encoding="utf-8")

    with pytest.raises(DuplicateProfileKeyError, match="duplicate JSON key"):
        read_profile_file(source)


@pytest.mark.parametrize(
    ("filename", "payload", "error_type"),
    [
        ("invalid.json", b"{}", ValidationError),
        ("invalid-utf8.json", b"\xff\xfe", UnicodeDecodeError),
        ("not-json.txt", b"{}", ValueError),
    ],
)
def test_profile_import_rejects_invalid_external_files(
    tmp_path: Path,
    filename: str,
    payload: bytes,
    error_type: type[Exception],
) -> None:
    source = tmp_path / filename
    source.write_bytes(payload)

    with pytest.raises(error_type):
        read_profile_file(source)


def test_profile_import_rejects_file_over_size_limit(tmp_path: Path) -> None:
    source = tmp_path / "oversized.json"
    source.write_bytes(b" " * (MAX_PROFILE_FILE_BYTES + 1))

    with pytest.raises(ValueError, match="256 KiB"):
        read_profile_file(source)


def test_profile_import_rejects_excessive_json_nesting(tmp_path: Path) -> None:
    source = tmp_path / "nested.json"
    source.write_text("[" * 1100 + "]" * 1100, encoding="utf-8")

    with pytest.raises(ValueError, match="nested too deeply"):
        read_profile_file(source)


def test_profile_import_rejects_directory_and_missing_path(tmp_path: Path) -> None:
    directory = tmp_path / "directory.json"
    directory.mkdir()

    with pytest.raises(ValueError, match="regular file"):
        read_profile_file(directory)
    with pytest.raises(FileNotFoundError):
        read_profile_file(tmp_path / "missing.json")


def test_profile_import_does_not_follow_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text(default_profile().model_dump_json(), encoding="utf-8")
    source = tmp_path / "linked.json"
    _symlink_or_skip(source, target)

    with pytest.raises(OSError, match="symlink or reparse"):
        read_profile_file(source)


def test_export_collision_requires_explicit_overwrite(tmp_path: Path) -> None:
    destination = tmp_path / "profile.json"
    destination.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        write_profile_file(default_profile(), destination)

    assert destination.read_text(encoding="utf-8") == "keep"
    write_profile_file(default_profile(), destination, overwrite=True)
    assert read_profile_file(destination) == default_profile()
    assert not tuple(tmp_path.glob("*.tmp"))


def test_export_rejects_non_json_and_missing_parent(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\.json"):
        write_profile_file(default_profile(), tmp_path / "profile.txt")
    with pytest.raises(FileNotFoundError):
        write_profile_file(default_profile(), tmp_path / "missing" / "profile.json")


def test_export_does_not_replace_symlink_destination(tmp_path: Path) -> None:
    sentinel = tmp_path / "outside.json"
    sentinel.write_text("keep", encoding="utf-8")
    destination = tmp_path / "profile.json"
    _symlink_or_skip(destination, sentinel)

    with pytest.raises(OSError, match="symlink or reparse"):
        write_profile_file(default_profile(), destination, overwrite=True)

    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert destination.is_symlink()


def test_failed_atomic_overwrite_preserves_destination_and_removes_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "profile.json"
    destination.write_text("keep", encoding="utf-8")

    def fail_replace(source: Path, target: Path) -> None:
        del source, target
        raise OSError("replace unavailable")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace unavailable"):
        write_profile_file(default_profile(), destination, overwrite=True)

    assert destination.read_text(encoding="utf-8") == "keep"
    assert not tuple(tmp_path.glob("*.tmp"))


def test_transfer_runtime_types_are_checked(tmp_path: Path) -> None:
    destination = tmp_path / "profile.json"

    with pytest.raises(TypeError, match="Expected BindingProfile"):
        write_profile_file(object(), destination)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"Expected pathlib\.Path"):
        read_profile_file("profile.json")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="overwrite must be a bool"):
        write_profile_file(default_profile(), destination, overwrite=1)  # type: ignore[arg-type]


def _symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")
