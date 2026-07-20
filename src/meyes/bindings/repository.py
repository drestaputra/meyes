"""Atomic fail-closed persistence for user binding profiles."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Callable
from contextlib import suppress
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


@dataclass(frozen=True, slots=True)
class ProfileCatalogResult:
    """Visible profile names plus a sanitized catalog warning."""

    names: tuple[str, ...]
    warning: str | None = None


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
            return ProfileLoadResult(self._read_profile_path(path, normalized))
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
        try:
            self._paths.ensure_directories()
        except OSError as error:
            raise OSError("Profile storage could not be prepared") from error
        self._assert_safe_profile_directory()
        path = self._profile_path(validated.profile_name)
        existing = self._find_profile_path(validated.profile_name)
        if existing is not None and existing.stem != validated.profile_name:
            raise ValueError("A profile with the same case-insensitive name already exists")
        self._assert_safe_profile_path(path)
        return self._replace_profile_path(validated, path)

    def create(self, profile: BindingProfile) -> Path:
        """Create one complete user profile through an exclusive destination."""
        if not isinstance(profile, BindingProfile):
            raise TypeError("Expected BindingProfile")
        validated = BindingProfile.model_validate(
            profile.model_dump(mode="python", warnings="none")
        )
        if validated.profile_name.casefold() == DEFAULT_PROFILE_NAME.casefold():
            raise ValueError("The built-in Default profile is immutable")
        try:
            self._paths.ensure_directories()
        except OSError as error:
            raise OSError("Profile storage could not be prepared") from error
        self._assert_safe_profile_directory()
        path = self._profile_path(validated.profile_name)
        self._assert_safe_profile_path(path)
        if self._find_profile_path(validated.profile_name) is not None:
            raise FileExistsError("A profile with that name already exists")
        serialized = f"{validated.model_dump_json(indent=2)}\n"
        created = False
        try:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                created = True
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as error:
            raise FileExistsError("A profile with that name already exists") from error
        except Exception:
            if created:
                path.unlink(missing_ok=True)
            raise
        return path

    def rename(self, profile_name: str, new_name: str) -> Path:
        """Create the renamed snapshot before retiring its inactive source file."""
        normalized = self._validate_user_profile_name(profile_name)
        renamed = self._validate_user_profile_name(new_name)
        if normalized.casefold() == renamed.casefold():
            raise ValueError("The new profile name must be different")
        self._prepare_profile_storage()
        source = self._find_profile_path(normalized)
        if source is None:
            raise FileNotFoundError("The profile was not found")
        self._assert_safe_profile_path(source)
        profile = self._read_profile_path(source, normalized)
        destination = self._profile_path(renamed)
        self._assert_safe_profile_path(destination)
        if self._find_profile_path(renamed) is not None:
            raise FileExistsError("A profile with that name already exists")

        renamed_profile = BindingProfile(
            profile_name=renamed,
            bindings=profile.bindings,
        )
        serialized = f"{renamed_profile.model_dump_json(indent=2)}\n"
        try:
            with destination.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as error:
            raise FileExistsError("A profile with that name already exists") from error
        try:
            self._assert_safe_profile_path(source)
            source.unlink()
        except Exception:
            with suppress(OSError):
                destination.unlink(missing_ok=True)
            raise
        return destination

    def delete(self, profile_name: str) -> Path:
        """Retire one user profile into a recoverable same-directory backup."""
        normalized = self._validate_user_profile_name(profile_name)
        self._prepare_profile_storage()
        source = self._find_profile_path(normalized)
        if source is None:
            raise FileNotFoundError("The profile was not found")
        self._assert_safe_profile_path(source)
        self._read_profile_path(source, normalized)
        stamp = self._clock().astimezone(UTC).strftime("%Y%m%d-%H%M%S-%f")
        backup = source.with_name(f"{source.stem}.deleted-{stamp}.bak")
        self._assert_safe_profile_path(backup)
        if backup.exists():
            raise FileExistsError("A recovery backup with that name already exists")
        source.replace(backup)
        return backup

    def restore_default(self, profile_name: str) -> Path:
        """Replace one user profile's bindings with the built-in Default bindings."""
        normalized = self._validate_user_profile_name(profile_name)
        self._prepare_profile_storage()
        source = self._find_profile_path(normalized)
        if source is None:
            raise FileNotFoundError("The profile was not found")
        current = self._read_profile_path(source, normalized)
        restored = BindingProfile(
            profile_name=current.profile_name,
            bindings=default_profile().bindings,
        )
        return self._replace_profile_path(restored, source)

    def catalog(self) -> ProfileCatalogResult:
        """Return valid names and disclose storage or validation problems."""
        try:
            self._paths.ensure_directories()
            self._assert_safe_profile_directory()
            paths = sorted(
                self._paths.profiles_dir.glob("*.json"),
                key=lambda item: item.name.casefold(),
            )
        except OSError:
            return ProfileCatalogResult(
                (DEFAULT_PROFILE_NAME,),
                warning="Profile storage could not be read.",
            )
        valid_names: dict[str, str | None] = {}
        skipped_file = False
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
                    if key in valid_names:
                        valid_names[key] = None
                        skipped_file = True
                    else:
                        valid_names[key] = profile.profile_name
                else:
                    skipped_file = True
            except (
                OSError,
                UnicodeError,
                json.JSONDecodeError,
                DuplicateJsonKeyError,
                ValidationError,
                ValueError,
            ):
                skipped_file = True
        names = [name for name in valid_names.values() if name is not None]
        warning = (
            "Some profile files were ignored because they are invalid or ambiguous."
            if skipped_file
            else None
        )
        return ProfileCatalogResult(
            (DEFAULT_PROFILE_NAME, *sorted(names, key=str.casefold)),
            warning=warning,
        )

    def list_profile_names(self) -> tuple[str, ...]:
        """Return the built-in profile plus valid persisted profile names."""
        return self.catalog().names

    def _profile_path(self, profile_name: str) -> Path:
        normalized = validate_profile_name(profile_name)
        return self._paths.profiles_dir / f"{normalized}.json"

    def _prepare_profile_storage(self) -> None:
        try:
            self._paths.ensure_directories()
        except OSError as error:
            raise OSError("Profile storage could not be prepared") from error
        self._assert_safe_profile_directory()

    @staticmethod
    def _validate_user_profile_name(profile_name: str) -> str:
        normalized = validate_profile_name(profile_name)
        if normalized.casefold() == DEFAULT_PROFILE_NAME.casefold():
            raise ValueError("The built-in Default profile is immutable")
        return normalized

    def _read_profile_path(self, path: Path, requested_name: str) -> BindingProfile:
        self._assert_safe_profile_path(path)
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
        profile = BindingProfile.model_validate(payload)
        if profile.profile_name.casefold() != requested_name.casefold():
            raise ValueError("profile name does not match its filename")
        return profile

    def _replace_profile_path(self, profile: BindingProfile, path: Path) -> Path:
        serialized = f"{profile.model_dump_json(indent=2)}\n"
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
