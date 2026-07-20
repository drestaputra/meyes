"""Fail-closed lifecycle coordination for accepted-calibration persistence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from meyes.calibration.acceptance import AcceptedCalibration, CalibrationAcceptancePolicy
from meyes.calibration.persistence import CalibrationLoadResult, CalibrationProvenance
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
    VOLATILE = "volatile"
    INCOMPATIBLE = "incompatible"
    FAULTED = "faulted"


@dataclass(frozen=True, slots=True)
class CalibrationPersistenceResult:
    status: CalibrationPersistenceStatus
    message: str
    provisioning: CursorProvisioningResult | None = None
    recovered_from: Path | None = None
    provenance: CalibrationProvenance | None = None


class CalibrationPersistenceLifecycle:
    """Order storage and fake-only provisioning without any Live Input dependency."""

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
    ) -> CalibrationPersistenceResult:
        """Clear old provisioning, validate current display, then persist accepted proof."""
        if calibration is not None and not isinstance(calibration, AcceptedCalibration):
            raise TypeError("Expected AcceptedCalibration or None")
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
        try:
            provenance = CalibrationProvenance(self._clock(), provisioning.geometry)
            self._store.save(calibration, self._policy, provenance)
        except (OSError, TypeError, ValueError):
            return CalibrationPersistenceResult(
                CalibrationPersistenceStatus.FAULTED,
                "Accepted calibration could not be saved; the current diagnostics are volatile.",
                provisioning,
            )
        return CalibrationPersistenceResult(
            CalibrationPersistenceStatus.SAVED,
            _provenance_message("Saved", provenance),
            provisioning,
            provenance=provenance,
        )


def _provenance_message(action: str, provenance: CalibrationProvenance) -> str:
    screen = provenance.primary_screen
    created = provenance.created_at_utc.strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{action} calibration from {created} for {screen.width}x{screen.height} "
        f"at ({screen.left}, {screen.top}); fake-only diagnostics configured."
    )
