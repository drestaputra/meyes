"""Bounded, schema-validated profile import and export files."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from meyes.bindings.models import BindingProfile

MAX_PROFILE_FILE_BYTES = 256 * 1024


class DuplicateProfileKeyError(ValueError):
    """Raised when an external profile JSON object contains a duplicate key."""


def read_profile_file(source: Path) -> BindingProfile:
    """Read one bounded regular UTF-8 JSON file and validate its complete schema."""
    _require_path(source)
    if source.suffix.casefold() != ".json":
        raise ValueError("Profile import must use a .json file")
    metadata = source.lstat()
    if _is_link_or_reparse(source):
        raise OSError("Profile import must not follow a symlink or reparse point")
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("Profile import must be a regular file")
    if metadata.st_size > MAX_PROFILE_FILE_BYTES:
        raise ValueError("Profile import exceeds the 256 KiB size limit")
    with source.open("rb") as stream:
        encoded = stream.read(MAX_PROFILE_FILE_BYTES + 1)
    if len(encoded) > MAX_PROFILE_FILE_BYTES:
        raise ValueError("Profile import exceeds the 256 KiB size limit")
    text = encoded.decode("utf-8")
    try:
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except RecursionError as error:
        raise ValueError("Profile JSON is nested too deeply") from error
    return BindingProfile.model_validate(payload)


def write_profile_file(
    profile: BindingProfile,
    destination: Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write a complete profile to an explicit JSON destination safely."""
    if not isinstance(profile, BindingProfile):
        raise TypeError("Expected BindingProfile")
    _require_path(destination)
    if not isinstance(overwrite, bool):
        raise TypeError("overwrite must be a bool")
    if destination.suffix.casefold() != ".json":
        raise ValueError("Profile export must use a .json file")
    parent = destination.parent
    parent_metadata = parent.lstat()
    if not stat.S_ISDIR(parent_metadata.st_mode):
        raise ValueError("Profile export destination must have an existing directory")
    _assert_safe_destination(destination)
    if destination.exists() and not overwrite:
        raise FileExistsError("The export file already exists")

    validated = BindingProfile.model_validate(profile.model_dump(mode="python", warnings="none"))
    serialized = f"{validated.model_dump_json(indent=2)}\n"
    if not overwrite:
        created = False
        try:
            with destination.open("x", encoding="utf-8", newline="\n") as stream:
                created = True
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            if created:
                destination.unlink(missing_ok=True)
            raise
        return destination

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-",
        suffix=".tmp",
        dir=parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            descriptor = -1
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        _assert_safe_destination(destination)
        os.replace(temporary, destination)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
    return destination


def _require_path(path: Path) -> None:
    if not isinstance(path, Path):
        raise TypeError("Expected pathlib.Path")


def _assert_safe_destination(destination: Path) -> None:
    if _is_link_or_reparse(destination):
        raise OSError("Profile export must not replace a symlink or reparse point")
    if destination.exists() and not destination.is_file():
        raise ValueError("Profile export destination must be a regular file")


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateProfileKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)
