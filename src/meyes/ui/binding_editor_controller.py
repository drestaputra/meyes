"""Qt-safe, no-execution binding draft and save-as-copy workflow."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Slot

from meyes.bindings.defaults import DEFAULT_PROFILE_NAME
from meyes.bindings.editor import EditableActionKind, parse_action
from meyes.bindings.manager import BindingManager
from meyes.bindings.models import BindableGesture, BindingProfile
from meyes.bindings.repository import BindingProfileRepository
from meyes.util.logging import get_logger
from meyes.util.profile_names import validate_profile_name


@dataclass(frozen=True, slots=True)
class BindingDraftState:
    """One immutable view of the isolated binding draft."""

    source_profile: BindingProfile
    draft_profile: BindingProfile
    active_profile_name: str
    errors: tuple[tuple[BindableGesture, str], ...]
    dirty: bool
    source_outdated: bool
    storage_available: bool

    @property
    def can_save(self) -> bool:
        """Report whether the current draft can be persisted as a copy."""
        return self.storage_available and not self.errors

    def error_for(self, gesture: BindableGesture) -> str | None:
        """Return the current sanitized validation error for one gesture."""
        if not isinstance(gesture, BindableGesture):
            raise TypeError("Expected BindableGesture")
        return dict(self.errors).get(gesture)


@dataclass(frozen=True, slots=True)
class BindingEditResult:
    """Sanitized result of editing or resetting one binding row."""

    success: bool
    gesture: BindableGesture
    message: str


@dataclass(frozen=True, slots=True)
class BindingSaveResult:
    """Sanitized result of a draft save-as-copy operation."""

    success: bool
    message: str
    profile_name: str | None = None


class BindingEditorController(QObject):
    """Own an isolated draft; never dispatch or activate its actions."""

    state_changed = Signal(object)
    operation_finished = Signal(object)
    profile_saved = Signal(object)

    def __init__(
        self,
        active_profile: BindingProfile,
        *,
        repository: BindingProfileRepository | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(active_profile, BindingProfile):
            raise TypeError("Expected BindingProfile")
        if repository is not None and not isinstance(repository, BindingProfileRepository):
            raise TypeError("Expected BindingProfileRepository")
        snapshot = _profile_copy(active_profile)
        self._active_profile = snapshot
        self._source_profile = snapshot
        self._draft_profile = snapshot
        self._errors: dict[BindableGesture, str] = {}
        self._repository = repository
        self._logger = get_logger("PROFILE")

    @property
    def state(self) -> BindingDraftState:
        """Return a detached snapshot of the complete editor state."""
        source = _profile_copy(self._source_profile)
        draft = _profile_copy(self._draft_profile)
        errors = tuple(
            (gesture, self._errors[gesture])
            for gesture in BindableGesture
            if gesture in self._errors
        )
        return BindingDraftState(
            source_profile=source,
            draft_profile=draft,
            active_profile_name=self._active_profile.profile_name,
            errors=errors,
            dirty=bool(errors) or draft.bindings != source.bindings,
            source_outdated=source != self._active_profile,
            storage_available=self._repository is not None,
        )

    def edit_binding(
        self,
        gesture: BindableGesture,
        kind: EditableActionKind,
        parameters: str,
    ) -> BindingEditResult:
        """Validate one row and update only the isolated draft on success."""
        if not isinstance(gesture, BindableGesture):
            raise TypeError("Expected BindableGesture")
        if not isinstance(kind, EditableActionKind):
            raise TypeError("Expected EditableActionKind")
        if not isinstance(parameters, str):
            raise TypeError("parameters must be a string")
        try:
            action = parse_action(gesture, kind, parameters)
            manager = BindingManager(self._draft_profile)
            self._draft_profile = manager.set_binding(gesture, action)
        except ValueError as error:
            message = str(error)
            self._errors[gesture] = message
            self._emit_state()
            return BindingEditResult(False, gesture, message)
        self._errors.pop(gesture, None)
        self._emit_state()
        return BindingEditResult(True, gesture, "Binding draft updated.")

    def reset_binding(self, gesture: BindableGesture) -> BindingEditResult:
        """Restore one draft row from its immutable source snapshot."""
        if not isinstance(gesture, BindableGesture):
            raise TypeError("Expected BindableGesture")
        manager = BindingManager(self._draft_profile)
        self._draft_profile = manager.set_binding(
            gesture,
            self._source_profile.bindings[gesture],
        )
        self._errors.pop(gesture, None)
        self._emit_state()
        return BindingEditResult(True, gesture, "Binding reset to the source snapshot.")

    def reset_all(self) -> None:
        """Restore the full isolated draft from its current source snapshot."""
        self._draft_profile = _profile_copy(self._source_profile)
        self._errors.clear()
        self._emit_state()

    def load_active(self) -> None:
        """Explicitly discard the draft and load the latest active runtime snapshot."""
        self._source_profile = _profile_copy(self._active_profile)
        self._draft_profile = _profile_copy(self._active_profile)
        self._errors.clear()
        self._emit_state()

    @Slot(object)
    def observe_active_profile(self, payload: object) -> None:
        """Rebase a clean draft, but preserve an edited draft when runtime changes."""
        active = binding_profile(payload)
        self._active_profile = _profile_copy(active)
        state = self.state
        if not state.dirty:
            self._source_profile = _profile_copy(active)
            self._draft_profile = _profile_copy(active)
            self._errors.clear()
        self._emit_state()

    def save_as_copy(self, profile_name: str) -> BindingSaveResult:
        """Persist the valid draft as a new profile without activating it."""
        if not isinstance(profile_name, str):
            raise TypeError("profile_name must be a string")
        if self._repository is None:
            return self._finish_save(
                BindingSaveResult(
                    False,
                    "Profile storage is unavailable; the draft was not saved.",
                )
            )
        if self._errors:
            return self._finish_save(
                BindingSaveResult(
                    False,
                    "Resolve every inline binding error before saving the draft.",
                )
            )
        try:
            normalized = validate_profile_name(profile_name)
        except ValueError:
            return self._finish_save(
                BindingSaveResult(
                    False,
                    "Use 1-80 characters and avoid Windows-reserved names or symbols.",
                )
            )
        if normalized.casefold() == DEFAULT_PROFILE_NAME.casefold():
            return self._finish_save(
                BindingSaveResult(
                    False,
                    "Default is built in. Choose a different name for the saved copy.",
                )
            )
        candidate = BindingProfile(
            schema_version=self._draft_profile.schema_version,
            profile_name=normalized,
            bindings=dict(self._draft_profile.bindings),
        )
        try:
            self._repository.create(candidate)
        except FileExistsError:
            return self._finish_save(
                BindingSaveResult(False, "A profile with that name already exists.")
            )
        except (OSError, ValueError):
            self._logger.error("binding_draft_save_failed", exc_info=True)
            return self._finish_save(
                BindingSaveResult(
                    False,
                    "The draft could not be saved. Check local profile storage and try again.",
                )
            )
        self._source_profile = _profile_copy(candidate)
        self._draft_profile = _profile_copy(candidate)
        self._errors.clear()
        self._emit_state()
        self.profile_saved.emit(_profile_copy(candidate))
        return self._finish_save(
            BindingSaveResult(
                True,
                "Saved a new local profile. It was not activated; runtime bindings are unchanged.",
                profile_name=candidate.profile_name,
            )
        )

    def _emit_state(self) -> None:
        self.state_changed.emit(self.state)

    def _finish_save(self, result: BindingSaveResult) -> BindingSaveResult:
        self.operation_finished.emit(result)
        return result


def binding_draft_state(payload: object) -> BindingDraftState:
    """Validate draft state crossing a Qt object signal."""
    if not isinstance(payload, BindingDraftState):
        raise TypeError("Expected BindingDraftState")
    return payload


def binding_save_result(payload: object) -> BindingSaveResult:
    """Validate a save result crossing a Qt object signal."""
    if not isinstance(payload, BindingSaveResult):
        raise TypeError("Expected BindingSaveResult")
    return payload


def binding_profile(payload: object) -> BindingProfile:
    """Validate a binding profile crossing a Qt object signal."""
    if not isinstance(payload, BindingProfile):
        raise TypeError("Expected BindingProfile")
    return payload


def _profile_copy(profile: BindingProfile) -> BindingProfile:
    return BindingManager(profile).active_profile
