"""Atomic fail-closed persistence for user binding profiles."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from meyes.bindings.defaults import DEFAULT_PROFILE_NAME, default_profile, disabled_profile
from meyes.bindings.models import BindingProfile
from meyes.util.paths import AppPaths
from meyes.util.profile_names import validate_profile_name

Clock = Callable[[], datetime]


class DuplicateJsonKeyError(ValueError):
    """Raised when a profile JSON object attempts to shadow an earlier key."""


@dataclass(frozen=True, slots=True)
class ProfileLoadResult:
    """Loaded profile plus fail-closed recovery information."""

    profile: BindingProfile
    warning: str | None = None
    recovered_from: Path | None = None


class BindingProfileRepository:
    """Load built-in defaults and persist Windows-safe user profiles."""

    def __init__(self, paths: AppPaths, clock: Clock | None = None) -> None:
        self._paths = paths
        self._clock = clock or (lambda: datetime.now(UTC))

    def load(self, profile_name: str) -> ProfileLoadResult:
        """Load one profile; invalid or missing user data becomes all-disabled."""
        try:
            normalized = validate_profile_name(profile_name)
        except ValueError as error:
            return ProfileLoadResult(
                disabled_profile("Invalid Profile"),
                warning=f"Binding profile name was invalid; all gestures are disabled: {error}",
            )
        if normalized.casefold() == DEFAULT_PROFILE_NAME.casefold():
            return ProfileLoadResult(default_profile())

        try:
            self._paths.ensure_directories()
            self._assert_safe_profile_directory()
            path = self._find_profile_path(normalized)
        except (OSError, ValueError) as error:
            return ProfileLoadResult(
                disabled_profile(normalized),
                warning=(
                    f"Binding profile '{normalized}' storage was unavailable or ambiguous; "
                    f"all gestures are disabled: {error}"
                ),
            )
        if path is None:
            return ProfileLoadResult(
                disabled_profile(normalized),
                warning=f"Binding profile '{normalized}' was not found; all gestures are disabled.",
            )

        try:
            self._assert_safe_profile_path(path)
            payload = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
            profile = BindingProfile.model_validate(payload)
            if profile.profile_name.casefold() != normalized.casefold():
                raise ValueError("profile name does not match its filename")
            return ProfileLoadResult(profile)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            DuplicateJsonKeyError,
            ValidationError,
            ValueError,
        ) as error:
            backup_path = self._backup_invalid_profile(path)
            return ProfileLoadResult(
                disabled_profile(normalized),
                warning=(
                    f"Binding profile '{normalized}' was invalid; all gestures are disabled: "
                    f"{error}"
                ),
                recovered_from=backup_path,
            )

    def save(self, profile: BindingProfile) -> Path:
        """Persist one non-default profile atomically as human-readable UTF-8 JSON."""
        if not isinstance(profile, BindingProfile):
            raise TypeError("Expected BindingProfile")
        validated = BindingProfile.model_validate(
            profile.model_dump(mode="python", warnings="none")
        )
        if validated.profile_name.casefold() == DEFAULT_PROFILE_NAME.casefold():
            raise ValueError("The built-in Default profile is immutable")
        self._paths.ensure_directories()
        self._assert_safe_profile_directory()
        path = self._profile_path(validated.profile_name)
        existing = self._find_profile_path(validated.profile_name)
        if existing is not None and existing.stem != validated.profile_name:
            raise ValueError("A profile with the same case-insensitive name already exists")
        self._assert_safe_profile_path(path)
        serialized = f"{validated.model_dump_json(indent=2)}\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.stem}-",
            suffix=".tmp",
            dir=self._paths.profiles_dir,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                descriptor = -1
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            self._assert_safe_profile_path(path)
            os.replace(temporary_path, path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary_path.unlink(missing_ok=True)
        return path

    def list_profile_names(self) -> tuple[str, ...]:
        """Return the built-in profile plus valid persisted profile names."""
        try:
            self._paths.ensure_directories()
            self._assert_safe_profile_directory()
            paths = sorted(
                self._paths.profiles_dir.glob("*.json"),
                key=lambda item: item.name.casefold(),
            )
        except OSError:
            return (DEFAULT_PROFILE_NAME,)
        valid_names: dict[str, str | None] = {}
        for path in paths:
            try:
                self._assert_safe_profile_path(path)
                payload = json.loads(
                    path.read_text(encoding="utf-8"),
                    object_pairs_hook=_reject_duplicate_keys,
                )
                profile = BindingProfile.model_validate(payload)
                key = profile.profile_name.casefold()
                if (
                    profile.profile_name.casefold() == path.stem.casefold()
                    and key != DEFAULT_PROFILE_NAME.casefold()
                ):
                    valid_names[key] = None if key in valid_names else profile.profile_name
            except (
                OSError,
                UnicodeError,
                json.JSONDecodeError,
                DuplicateJsonKeyError,
                ValidationError,
                ValueError,
            ):
                continue
        names = [name for name in valid_names.values() if name is not None]
        return (DEFAULT_PROFILE_NAME, *sorted(names, key=str.casefold))

    def _profile_path(self, profile_name: str) -> Path:
        normalized = validate_profile_name(profile_name)
        return self._paths.profiles_dir / f"{normalized}.json"

    def _find_profile_path(self, profile_name: str) -> Path | None:
        expected = validate_profile_name(profile_name).casefold()
        matches = sorted(
            (
                path
                for path in self._paths.profiles_dir.glob("*.json")
                if path.stem.casefold() == expected
            ),
            key=lambda item: item.name,
        )
        if len(matches) > 1:
            raise ValueError("Multiple profiles use the same case-insensitive name")
        return matches[0] if matches else None

    def _assert_safe_profile_path(self, path: Path) -> None:
        self._assert_safe_profile_directory()
        root = self._paths.profiles_dir.resolve(strict=True)
        if path.parent.resolve(strict=True) != root:
            raise OSError("profile path escapes the configured profile directory")
        if _is_link_or_reparse(path):
            raise OSError("profile path must not be a symlink or reparse point")

    def _assert_safe_profile_directory(self) -> None:
        if _is_link_or_reparse(self._paths.profiles_dir):
            raise OSError("profile directory must not be a symlink or reparse point")

    def _backup_invalid_profile(self, path: Path) -> Path | None:
        try:
            path.lstat()
        except OSError:
            return None
        stamp = self._clock().astimezone(UTC).strftime("%Y%m%d-%H%M%S-%f")
        backup_path = path.with_name(f"{path.stem}.invalid-{stamp}.bak")
        try:
            backup_path.lstat()
        except FileNotFoundError:
            pass
        except OSError:
            return None
        else:
            return None
        try:
            path.replace(backup_path)
        except OSError:
            return None
        return backup_path


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key}")
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
