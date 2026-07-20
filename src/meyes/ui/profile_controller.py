"""Qt-safe profile catalog and fail-closed runtime activation workflow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from meyes.bindings.defaults import DEFAULT_PROFILE_NAME, default_profile, disabled_profile
from meyes.bindings.manager import BindingManager
from meyes.bindings.models import BindingProfile
from meyes.bindings.repository import BindingProfileRepository
from meyes.ui.action_simulation import ActionSimulationController
from meyes.util.logging import get_logger
from meyes.util.profile_names import validate_profile_name

PersistActiveProfile = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class ProfileOperationResult:
    """Sanitized result for a user-initiated profile operation."""

    success: bool
    message: str
    profile_name: str | None = None
    warning: bool = False


class ProfileController(QObject):
    """Coordinate durable profiles with the paused fake-only runtime."""

    profiles_changed = Signal(object)
    active_profile_changed = Signal(object)
    operation_finished = Signal(object)

    def __init__(
        self,
        active_profile: BindingProfile,
        simulation: ActionSimulationController,
        *,
        repository: BindingProfileRepository | None = None,
        persist_active_profile: PersistActiveProfile | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(active_profile, BindingProfile):
            raise TypeError("Expected BindingProfile")
        if not isinstance(simulation, ActionSimulationController):
            raise TypeError("Expected ActionSimulationController")
        if repository is not None and not isinstance(repository, BindingProfileRepository):
            raise TypeError("Expected BindingProfileRepository")
        if persist_active_profile is not None and not callable(persist_active_profile):
            raise TypeError("persist_active_profile must be callable")
        self._active_profile = BindingManager(active_profile).active_profile
        self._simulation = simulation
        if self._simulation.active_profile != self._active_profile:
            raise ValueError("Runtime and profile controller snapshots must match")
        self._repository = repository
        self._persist_active_profile = persist_active_profile
        self._profile_names, self._catalog_warning = self._initial_catalog()
        self._logger = get_logger("PROFILE")

    @property
    def can_manage(self) -> bool:
        """Report whether durable create and activation operations are available."""
        return self._repository is not None and self._persist_active_profile is not None

    @property
    def storage_available(self) -> bool:
        """Report whether the profile repository is available for catalog refresh."""
        return self._repository is not None

    @property
    def catalog_warning(self) -> str | None:
        """Return a sanitized warning discovered during the latest catalog read."""
        return self._catalog_warning

    @property
    def active_profile(self) -> BindingProfile:
        """Return an isolated copy of the active runtime profile."""
        return BindingManager(self._active_profile).active_profile

    @property
    def profile_names(self) -> tuple[str, ...]:
        """Return the current stable catalog view."""
        return self._profile_names

    def refresh(self) -> ProfileOperationResult:
        """Refresh the visible catalog without changing runtime state."""
        if self._repository is None:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "Profile storage is unavailable in this session.",
                    warning=True,
                )
            )
        warning = self.synchronize_catalog()
        if warning:
            return self._finish(
                ProfileOperationResult(
                    True,
                    warning,
                    warning=True,
                )
            )
        return self._finish(ProfileOperationResult(True, "Profile list refreshed."))

    def synchronize_catalog(self) -> str | None:
        """Refresh catalog state without emitting user-operation feedback."""
        if self._repository is None:
            self._catalog_warning = "Profile storage is unavailable in this session."
            return self._catalog_warning
        catalog = self._repository.catalog()
        names, warning = self._catalog_state(catalog.names, catalog.warning)
        self._catalog_warning = warning
        self._set_profile_names(names)
        return warning

    def create_disabled(self, profile_name: str) -> ProfileOperationResult:
        """Create a complete all-disabled profile without activating it."""
        if not self.can_manage or self._repository is None:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "Profile changes are unavailable in this session.",
                )
            )
        try:
            normalized = validate_profile_name(profile_name)
            profile = disabled_profile(normalized)
            self._repository.create(profile)
        except FileExistsError:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "A profile with that name already exists.",
                )
            )
        except ValueError:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "Use 1-80 characters and avoid Windows-reserved names or symbols.",
                )
            )
        except OSError:
            self._logger.error("profile_create_failed", exc_info=True)
            return self._finish(
                ProfileOperationResult(
                    False,
                    "The profile could not be saved. Check local storage access and try again.",
                )
            )
        self._set_profile_names((*self._profile_names, profile.profile_name))
        return self._finish(
            ProfileOperationResult(
                True,
                "Created the new profile with all gestures disabled.",
                profile_name=profile.profile_name,
            )
        )

    def rename(self, profile_name: str, new_name: str) -> ProfileOperationResult:
        """Rename one inactive user profile without changing runtime state."""
        unavailable = self._lifecycle_unavailable()
        if unavailable is not None:
            return unavailable
        selected = self._inactive_user_profile(profile_name, "rename")
        if isinstance(selected, ProfileOperationResult):
            return selected
        try:
            renamed = validate_profile_name(new_name)
        except ValueError:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "Use 1-80 characters and avoid Windows-reserved names or symbols.",
                )
            )
        if renamed.casefold() == selected.casefold():
            return self._finish(
                ProfileOperationResult(
                    True,
                    "The selected profile already uses that case-insensitive name.",
                    profile_name=selected,
                )
            )
        if renamed.casefold() == DEFAULT_PROFILE_NAME.casefold():
            return self._finish(
                ProfileOperationResult(False, "The built-in Default profile is immutable.")
            )

        assert self._repository is not None
        try:
            self._repository.rename(selected, renamed)
        except FileExistsError:
            return self._finish(
                ProfileOperationResult(False, "A profile with that name already exists.")
            )
        except FileNotFoundError:
            self.synchronize_catalog()
            return self._finish(
                ProfileOperationResult(
                    False,
                    "The selected profile no longer exists. The profile list was refreshed.",
                    warning=True,
                )
            )
        except (OSError, UnicodeError, ValueError):
            self._logger.error("profile_rename_failed", exc_info=True)
            self.synchronize_catalog()
            return self._finish(
                ProfileOperationResult(
                    False,
                    "The profile could not be renamed safely. Check local storage access "
                    "and refresh the list.",
                )
            )
        self.synchronize_catalog()
        return self._finish(
            ProfileOperationResult(
                True,
                f"Renamed the inactive profile to '{renamed}'.",
                profile_name=renamed,
            )
        )

    def delete(self, profile_name: str, confirmation: str) -> ProfileOperationResult:
        """Retire one inactive user profile after an exact-name confirmation."""
        unavailable = self._lifecycle_unavailable()
        if unavailable is not None:
            return unavailable
        selected = self._inactive_user_profile(profile_name, "delete")
        if isinstance(selected, ProfileOperationResult):
            return selected
        if confirmation != selected:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "Type the selected profile name exactly to confirm deletion.",
                )
            )

        assert self._repository is not None
        try:
            self._repository.delete(selected)
        except FileNotFoundError:
            self.synchronize_catalog()
            return self._finish(
                ProfileOperationResult(
                    False,
                    "The selected profile no longer exists. The profile list was refreshed.",
                    warning=True,
                )
            )
        except (OSError, UnicodeError, ValueError):
            self._logger.error("profile_delete_failed", exc_info=True)
            self.synchronize_catalog()
            return self._finish(
                ProfileOperationResult(
                    False,
                    "The profile could not be deleted safely. Check local storage access "
                    "and refresh the list.",
                )
            )
        self.synchronize_catalog()
        return self._finish(
            ProfileOperationResult(
                True,
                "Deleted the inactive profile. A local recovery backup was retained.",
            )
        )

    def restore_default(
        self,
        profile_name: str,
        *,
        confirmed: bool,
    ) -> ProfileOperationResult:
        """Restore Default bindings into one confirmed inactive user profile."""
        unavailable = self._lifecycle_unavailable()
        if unavailable is not None:
            return unavailable
        selected = self._inactive_user_profile(profile_name, "restore")
        if isinstance(selected, ProfileOperationResult):
            return selected
        if confirmed is not True:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "Confirm that all six bindings may be replaced before restoring Default.",
                )
            )

        assert self._repository is not None
        try:
            self._repository.restore_default(selected)
        except FileNotFoundError:
            self.synchronize_catalog()
            return self._finish(
                ProfileOperationResult(
                    False,
                    "The selected profile no longer exists. The profile list was refreshed.",
                    warning=True,
                )
            )
        except (OSError, UnicodeError, ValueError):
            self._logger.error("profile_restore_default_failed", exc_info=True)
            self.synchronize_catalog()
            return self._finish(
                ProfileOperationResult(
                    False,
                    "Default bindings could not be restored safely. Check local storage "
                    "access and refresh the list.",
                )
            )
        return self._finish(
            ProfileOperationResult(
                True,
                "Restored all six bindings from the built-in Default snapshot. The profile "
                "remains inactive.",
                profile_name=selected,
            )
        )

    def activate(self, profile_name: str) -> ProfileOperationResult:
        """Pause, load, activate, and persist one profile transactionally."""
        if not self.can_manage or self._repository is None:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "Profile activation is unavailable in this session.",
                )
            )
        try:
            normalized = validate_profile_name(profile_name)
        except ValueError:
            return self._finish(ProfileOperationResult(False, "That profile name is invalid."))
        if normalized.casefold() == self._active_profile.profile_name.casefold():
            return self._finish(
                ProfileOperationResult(
                    True,
                    "The selected profile is already active.",
                    profile_name=self._active_profile.profile_name,
                )
            )

        paused = self._simulation.pause("profile transition")
        if not paused.success:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "Tracking could not be paused safely. Review Diagnostics and try again.",
                )
            )
        self._simulation.pause_tracking()

        loaded = self._repository.load(normalized)
        if loaded.warning:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "The profile could not be loaded. The previous profile remains "
                    "selected and tracking is paused.",
                )
            )
        candidate = loaded.profile
        if (
            candidate.profile_name.casefold() == DEFAULT_PROFILE_NAME.casefold()
            and candidate != default_profile()
        ):
            return self._finish(
                ProfileOperationResult(
                    False,
                    "The built-in Default profile cannot be modified.",
                )
            )

        previous = self.active_profile
        activated = self._simulation.activate_profile(candidate)
        if not activated.success:
            return self._finish(
                ProfileOperationResult(
                    False,
                    "The profile could not be activated safely. Review Diagnostics "
                    "before continuing.",
                )
            )

        assert self._persist_active_profile is not None
        try:
            self._persist_active_profile(candidate.profile_name)
        except Exception:
            self._logger.error("active_profile_persist_failed", exc_info=True)
            rolled_back = self._simulation.activate_profile(previous)
            if rolled_back.success:
                return self._finish(
                    ProfileOperationResult(
                        False,
                        "The active profile preference could not be saved. The previous "
                        "profile was restored and tracking remains paused.",
                    )
                )
            actual = self._simulation.active_profile
            self._active_profile = BindingManager(actual).active_profile
            self.active_profile_changed.emit(self.active_profile)
            self._set_profile_names(self._profile_names)
            return self._finish(
                ProfileOperationResult(
                    False,
                    "The active profile preference could not be saved, and the previous "
                    "runtime profile could not be restored. The selected profile remains loaded "
                    "in a fail-closed simulator; review Diagnostics before continuing.",
                    profile_name=actual.profile_name,
                    warning=True,
                )
            )

        self._active_profile = BindingManager(candidate).active_profile
        self.active_profile_changed.emit(self.active_profile)
        self._set_profile_names(self._profile_names)
        return self._finish(
            ProfileOperationResult(
                True,
                "The selected profile is active. Tracking remains paused until you resume it.",
                profile_name=candidate.profile_name,
            )
        )

    def _lifecycle_unavailable(self) -> ProfileOperationResult | None:
        if self.can_manage and self._repository is not None:
            return None
        return self._finish(
            ProfileOperationResult(
                False,
                "Profile lifecycle changes are unavailable in this session.",
            )
        )

    def _inactive_user_profile(
        self,
        profile_name: str,
        operation: str,
    ) -> str | ProfileOperationResult:
        try:
            normalized = validate_profile_name(profile_name)
        except ValueError:
            return self._finish(
                ProfileOperationResult(False, "The selected profile name is invalid.")
            )
        if normalized.casefold() == DEFAULT_PROFILE_NAME.casefold():
            return self._finish(
                ProfileOperationResult(False, "The built-in Default profile is immutable.")
            )
        if normalized.casefold() == self._active_profile.profile_name.casefold():
            return self._finish(
                ProfileOperationResult(
                    False,
                    f"Activate another profile before you {operation} this profile.",
                )
            )
        return normalized

    def _initial_catalog(self) -> tuple[tuple[str, ...], str | None]:
        if self._repository is None:
            return (
                self._normalized_names((DEFAULT_PROFILE_NAME, self._active_profile.profile_name)),
                "Profile storage is unavailable in this session.",
            )
        catalog = self._repository.catalog()
        return self._catalog_state(catalog.names, catalog.warning)

    def _catalog_state(
        self,
        names: tuple[str, ...],
        warning: str | None,
    ) -> tuple[tuple[str, ...], str | None]:
        active_is_stored = any(
            name.casefold() == self._active_profile.profile_name.casefold() for name in names
        )
        warnings = tuple(
            item
            for item in (
                warning,
                (
                    "The active profile is a recovery snapshot that is not stored in the "
                    "local catalog. Review the profile files before resuming tracking."
                    if not active_is_stored
                    else None
                ),
            )
            if item is not None
        )
        return self._normalized_names(names), " ".join(warnings) or None

    def _set_profile_names(self, names: tuple[str, ...]) -> None:
        normalized = self._normalized_names(names)
        if normalized == self._profile_names:
            return
        self._profile_names = normalized
        self.profiles_changed.emit(normalized)

    @staticmethod
    def _normalized_names(names: tuple[str, ...]) -> tuple[str, ...]:
        unique: dict[str, str] = {}
        for name in names:
            unique.setdefault(name.casefold(), name)
        default = unique.pop(DEFAULT_PROFILE_NAME.casefold(), DEFAULT_PROFILE_NAME)
        return (default, *sorted(unique.values(), key=str.casefold))

    def _finish(self, result: ProfileOperationResult) -> ProfileOperationResult:
        self.operation_finished.emit(result)
        return result


def profile_operation(payload: object) -> ProfileOperationResult:
    """Validate an operation result crossing a Qt object signal."""
    if not isinstance(payload, ProfileOperationResult):
        raise TypeError("Expected ProfileOperationResult")
    return payload


def profile_names(payload: object) -> tuple[str, ...]:
    """Validate a profile-name catalog crossing a Qt object signal."""
    if not isinstance(payload, tuple) or not all(isinstance(item, str) for item in payload):
        raise TypeError("Expected tuple of profile names")
    return payload


def binding_profile(payload: object) -> BindingProfile:
    """Validate a binding profile crossing a Qt object signal."""
    if not isinstance(payload, BindingProfile):
        raise TypeError("Expected BindingProfile")
    return payload
