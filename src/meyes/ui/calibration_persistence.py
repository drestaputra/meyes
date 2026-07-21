"""Fail-closed lifecycle coordination for accepted-calibration persistence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from meyes.calibration.acceptance import AcceptedCalibration, CalibrationAcceptancePolicy
from meyes.calibration.persistence import (
    CalibrationLoadResult,
    CalibrationProvenance,
    DeletedCalibrationBackup,
    DeletedCalibrationCatalog,
)
from meyes.ui.cursor_provisioning import (
    CursorProvisioningResult,
    CursorProvisioningStatus,
)


@runtime_checkable
class AcceptedCalibrationStore(Protocol):
    """Persistence operations needed by the lifecycle coordinator."""

    def save(
        self,
        calibration: AcceptedCalibration,
        policy: CalibrationAcceptancePolicy,
        provenance: CalibrationProvenance,
    ) -> Path: ...

    def load(
        self,
        policy: CalibrationAcceptancePolicy | None,
    ) -> CalibrationLoadResult: ...

    def forget(self) -> Path | None: ...

    def deleted_catalog(self) -> DeletedCalibrationCatalog: ...

    def restore(
        self,
        backup: DeletedCalibrationBackup,
        policy: CalibrationAcceptancePolicy | None,
    ) -> CalibrationLoadResult: ...

    def rollback_restored(self, backup: DeletedCalibrationBackup) -> bool: ...


@runtime_checkable
class CursorProvisioner(Protocol):
    """No-executor provisioning operation needed by the lifecycle coordinator."""

    def configure(
        self,
        calibration: AcceptedCalibration | None,
    ) -> CursorProvisioningResult: ...


class CalibrationPersistenceStatus(StrEnum):
    DISABLED = "disabled"
    EMPTY = "empty"
    RECOVERED = "recovered"
    SAVED = "saved"
    PENDING_REPLACE = "pending_replace"
    VOLATILE = "volatile"
    INCOMPATIBLE = "incompatible"
    FORGOTTEN = "forgotten"
    RESTORED = "restored"
    FAULTED = "faulted"


@dataclass(frozen=True, slots=True)
class CalibrationPersistenceResult:
    status: CalibrationPersistenceStatus
    message: str
    provisioning: CursorProvisioningResult | None = None
    recovered_from: Path | None = None
    provenance: CalibrationProvenance | None = None


class CalibrationPersistenceLifecycle:
    """Order storage and cursor provisioning without altering Live Input state."""

    def __init__(
        self,
        provisioner: CursorProvisioner,
        store: AcceptedCalibrationStore | None,
        policy: CalibrationAcceptancePolicy | None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(provisioner, CursorProvisioner):
            raise TypeError("Expected CursorProvisioner")
        if store is not None and not isinstance(store, AcceptedCalibrationStore):
            raise TypeError("Expected AcceptedCalibrationStore or None")
        if policy is not None and not isinstance(policy, CalibrationAcceptancePolicy):
            raise TypeError("Expected CalibrationAcceptancePolicy or None")
        self._provisioner = provisioner
        self._store = store
        self._policy = policy
        self._clock = clock or (lambda: datetime.now(UTC))
        self._recovery_result: CalibrationPersistenceResult | None = None
        self._has_saved_calibration = False

    @property
    def has_saved_calibration(self) -> bool:
        """Whether lifecycle evidence says an active stored envelope exists."""

        return self._has_saved_calibration

    def recover_once(self) -> CalibrationPersistenceResult:
        """Attempt startup recovery once, caching the conservative outcome."""
        if self._recovery_result is not None:
            return self._recovery_result
        if self._store is None:
            provisioning = self._provisioner.configure(None)
            result = CalibrationPersistenceResult(
                CalibrationPersistenceStatus.DISABLED,
                "Calibration persistence is unavailable; diagnostics remain unconfigured.",
                provisioning,
            )
        else:
            loaded = self._store.load(self._policy)
            self._has_saved_calibration = loaded.calibration is not None
            if loaded.calibration is None:
                provisioning = self._provisioner.configure(None)
                result = CalibrationPersistenceResult(
                    (
                        CalibrationPersistenceStatus.FAULTED
                        if loaded.recovered_from is not None
                        else CalibrationPersistenceStatus.EMPTY
                    ),
                    loaded.warning or "No accepted calibration is stored.",
                    provisioning,
                    loaded.recovered_from,
                )
            else:
                provisioning = self._provisioner.configure(loaded.calibration)
                if (
                    provisioning.status is not CursorProvisioningStatus.READY
                    or provisioning.geometry is None
                    or loaded.provenance is None
                ):
                    result = CalibrationPersistenceResult(
                        CalibrationPersistenceStatus.FAULTED,
                        provisioning.message,
                        provisioning,
                    )
                elif provisioning.geometry != loaded.provenance.primary_screen:
                    cleared = self._provisioner.configure(None)
                    result = CalibrationPersistenceResult(
                        CalibrationPersistenceStatus.INCOMPATIBLE,
                        "Stored calibration display geometry differs; recalibrate.",
                        cleared,
                        provenance=loaded.provenance,
                    )
                else:
                    result = CalibrationPersistenceResult(
                        CalibrationPersistenceStatus.RECOVERED,
                        _provenance_message("Recovered", loaded.provenance),
                        provisioning,
                        provenance=loaded.provenance,
                    )
        self._recovery_result = result
        return result

    def replace(
        self,
        calibration: AcceptedCalibration | None,
        *,
        confirm_existing: bool = False,
    ) -> CalibrationPersistenceResult:
        """Clear old provisioning, validate current display, then persist accepted proof."""
        if calibration is not None and not isinstance(calibration, AcceptedCalibration):
            raise TypeError("Expected AcceptedCalibration or None")
        if not isinstance(confirm_existing, bool):
            raise TypeError("confirm_existing must be a bool")
        cleared = self._provisioner.configure(None)
        if calibration is None:
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.EMPTY,
                "No accepted volatile calibration is available to persist.",
                cleared,
            )
        if self._store is None or self._policy is None:
            provisioning = self._provisioner.configure(calibration)
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.VOLATILE,
                "Accepted calibration remains volatile because persistence is unavailable.",
                provisioning,
            )
        provisioning = self._provisioner.configure(calibration)
        if (
            provisioning.status is not CursorProvisioningStatus.READY
            or provisioning.geometry is None
        ):
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.FAULTED,
                provisioning.message,
                provisioning,
            )
        if self._has_saved_calibration and not confirm_existing:
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.PENDING_REPLACE,
                "Accepted calibration is active only for this session; explicit confirmation "
                "is required before replacing the saved calibration.",
                provisioning,
            )
        try:
            provenance = CalibrationProvenance(self._clock(), provisioning.geometry)
            self._store.save(calibration, self._policy, provenance)
        except (OSError, TypeError, ValueError):
            if self._has_saved_calibration:
                return CalibrationPersistenceResult(
                    CalibrationPersistenceStatus.PENDING_REPLACE,
                    "Saved calibration replacement failed; the prior envelope remains intact "
                    "and explicit confirmation can be retried.",
                    provisioning,
                )
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.FAULTED,
                "Accepted calibration could not be saved; the current diagnostics are volatile.",
                provisioning,
            )
        self._has_saved_calibration = True
        return CalibrationPersistenceResult(
            CalibrationPersistenceStatus.SAVED,
            _provenance_message("Saved", provenance),
            provisioning,
            provenance=provenance,
        )

    def forget(self) -> CalibrationPersistenceResult:
        """Clear cursor provisioning before recoverably moving the stored envelope."""
        cleared = self._provisioner.configure(None)
        if self._store is None:
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.DISABLED,
                "Calibration persistence is unavailable; cursor diagnostics were cleared.",
                cleared,
            )
        try:
            backup = self._store.forget()
        except OSError:
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.FAULTED,
                "Saved calibration could not be forgotten; cursor diagnostics remain cleared.",
                cleared,
            )
        if backup is None:
            self._has_saved_calibration = False
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.EMPTY,
                "No saved calibration existed; cursor diagnostics were cleared.",
                cleared,
            )
        self._has_saved_calibration = False
        return CalibrationPersistenceResult(
            CalibrationPersistenceStatus.FORGOTTEN,
            "Saved calibration was moved to a recoverable deleted backup.",
            cleared,
            recovered_from=backup,
        )

    def deleted_catalog(self) -> DeletedCalibrationCatalog:
        """Expose bounded repository metadata without adding mutation."""
        if self._store is None:
            return DeletedCalibrationCatalog((), "Calibration persistence is unavailable.")
        return self._store.deleted_catalog()

    def restore(self, backup: DeletedCalibrationBackup) -> CalibrationPersistenceResult:
        """Restore, provision against current geometry, or roll the active copy back."""
        if not isinstance(backup, DeletedCalibrationBackup):
            raise TypeError("Expected DeletedCalibrationBackup")
        cleared = self._provisioner.configure(None)
        if self._store is None:
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.DISABLED,
                "Calibration persistence is unavailable; cursor diagnostics were cleared.",
                cleared,
            )
        try:
            loaded = self._store.restore(backup, self._policy)
        except (OSError, TypeError, ValueError):
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.FAULTED,
                "Deleted calibration backup could not be restored safely.",
                cleared,
            )
        if loaded.calibration is None or loaded.provenance is None:
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.FAULTED,
                loaded.warning or "Deleted calibration backup remains inactive.",
                cleared,
            )
        provisioning = self._provisioner.configure(loaded.calibration)
        geometry_matches = (
            provisioning.status is CursorProvisioningStatus.READY
            and provisioning.geometry == loaded.provenance.primary_screen
        )
        if not geometry_matches:
            self._provisioner.configure(None)
            try:
                rolled_back = self._store.rollback_restored(backup)
            except (OSError, TypeError, ValueError):
                rolled_back = False
            if not rolled_back:
                self._has_saved_calibration = True
                return CalibrationPersistenceResult(
                    CalibrationPersistenceStatus.FAULTED,
                    "Restore validation failed and the active copy needs manual review.",
                    cleared,
                    provenance=loaded.provenance,
                )
            self._has_saved_calibration = False
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.INCOMPATIBLE,
                "Deleted calibration display geometry differs; restore was rolled back.",
                cleared,
                provenance=loaded.provenance,
            )
        self._has_saved_calibration = True
        return CalibrationPersistenceResult(
            CalibrationPersistenceStatus.RESTORED,
            _provenance_message("Restored", loaded.provenance),
            provisioning,
            provenance=loaded.provenance,
        )


def _provenance_message(action: str, provenance: CalibrationProvenance) -> str:
    screen = provenance.primary_screen
    created = provenance.created_at_utc.strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{action} calibration from {created} for {screen.width}x{screen.height} "
        f"at ({screen.left}, {screen.top}); cursor pipeline configured."
    )
