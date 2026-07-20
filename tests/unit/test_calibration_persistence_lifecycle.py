from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from meyes.calibration.acceptance import (
    AcceptedCalibration,
    CalibrationAcceptance,
    CalibrationAcceptancePolicy,
    CalibrationAcceptanceState,
)
from meyes.calibration.mapper import (
    CalibrationFitResult,
    CalibrationValidation,
    PolynomialCalibrationMapper,
)
from meyes.calibration.persistence import CalibrationLoadResult, CalibrationProvenance
from meyes.cursor.screen_mapping import PhysicalScreenGeometry
from meyes.ui.calibration_persistence import (
    CalibrationPersistenceLifecycle,
    CalibrationPersistenceStatus,
)
from meyes.ui.cursor_diagnostics import CursorDiagnosticsController
from meyes.ui.cursor_provisioning import (
    CursorPipelineProvisioner,
    CursorProvisioningResult,
    CursorProvisioningStatus,
)


def _accepted() -> AcceptedCalibration:
    mapper = PolynomialCalibrationMapper(
        (0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    )
    fit = CalibrationFitResult(mapper, CalibrationValidation(18, 0.02, 0.015, 0.04))
    return AcceptedCalibration(
        fit,
        CalibrationAcceptance(CalibrationAcceptanceState.ACCEPTED),
    )


def _policy() -> CalibrationAcceptancePolicy:
    return CalibrationAcceptancePolicy(0.05, 0.04, 0.1, 18)


_CREATED_AT = datetime(2026, 7, 20, 8, 15, tzinfo=UTC)
_SCREEN = PhysicalScreenGeometry(0, 0, 1920, 1080)


def _provenance(screen: PhysicalScreenGeometry = _SCREEN) -> CalibrationProvenance:
    return CalibrationProvenance(_CREATED_AT, screen)


@dataclass
class _RecordingProvisioner:
    calls: list[object]
    geometry: PhysicalScreenGeometry = _SCREEN

    def configure(self, calibration: AcceptedCalibration | None) -> CursorProvisioningResult:
        self.calls.append(("configure", calibration))
        return CursorProvisioningResult(
            (
                CursorProvisioningStatus.READY
                if calibration is not None
                else CursorProvisioningStatus.UNAVAILABLE
            ),
            "configured" if calibration is not None else "cleared",
            self.geometry if calibration is not None else None,
        )


@dataclass
class _RecordingStore:
    calls: list[object]
    loaded: CalibrationLoadResult = field(default_factory=lambda: CalibrationLoadResult(None))
    save_error: OSError | None = None

    def save(
        self,
        calibration: AcceptedCalibration,
        policy: CalibrationAcceptancePolicy,
        provenance: CalibrationProvenance,
    ) -> Path:
        self.calls.append(("save", calibration, policy, provenance))
        if self.save_error is not None:
            raise self.save_error
        return Path("accepted-calibration.json")

    def load(
        self,
        policy: CalibrationAcceptancePolicy | None,
    ) -> CalibrationLoadResult:
        self.calls.append(("load", policy))
        return self.loaded


@dataclass
class _GeometryProvider:
    def read(self) -> PhysicalScreenGeometry:
        return PhysicalScreenGeometry(0, 0, 1920, 1080)


def test_replace_clears_before_save_and_reprovisions_afterward() -> None:
    calls: list[object] = []
    accepted = _accepted()
    policy = _policy()
    lifecycle = CalibrationPersistenceLifecycle(
        _RecordingProvisioner(calls),
        _RecordingStore(calls),
        policy,
        clock=lambda: _CREATED_AT,
    )

    result = lifecycle.replace(accepted)

    assert result.status is CalibrationPersistenceStatus.SAVED
    assert calls == [
        ("configure", None),
        ("configure", accepted),
        ("save", accepted, policy, _provenance()),
    ]


def test_save_fault_restores_only_volatile_fake_diagnostics() -> None:
    calls: list[object] = []
    accepted = _accepted()
    lifecycle = CalibrationPersistenceLifecycle(
        _RecordingProvisioner(calls),
        _RecordingStore(calls, save_error=OSError("disk unavailable")),
        _policy(),
        clock=lambda: _CREATED_AT,
    )

    result = lifecycle.replace(accepted)

    assert result.status is CalibrationPersistenceStatus.FAULTED
    assert "volatile" in result.message
    assert calls[:2] == [("configure", None), ("configure", accepted)]
    assert calls[-1] == ("save", accepted, _policy(), _provenance())


def test_missing_acceptance_clears_without_writing() -> None:
    calls: list[object] = []
    lifecycle = CalibrationPersistenceLifecycle(
        _RecordingProvisioner(calls),
        _RecordingStore(calls),
        _policy(),
    )

    result = lifecycle.replace(None)

    assert result.status is CalibrationPersistenceStatus.EMPTY
    assert calls == [("configure", None)]


def test_recovery_is_one_shot_and_configures_recovered_proof() -> None:
    calls: list[object] = []
    accepted = _accepted()
    policy = _policy()
    lifecycle = CalibrationPersistenceLifecycle(
        _RecordingProvisioner(calls),
        _RecordingStore(
            calls,
            loaded=CalibrationLoadResult(accepted, provenance=_provenance()),
        ),
        policy,
    )

    first = lifecycle.recover_once()
    second = lifecycle.recover_once()

    assert first is second
    assert first.status is CalibrationPersistenceStatus.RECOVERED
    assert calls == [("load", policy), ("configure", accepted)]


def test_invalid_recovery_clears_pipeline_and_retains_quarantine_path() -> None:
    calls: list[object] = []
    backup = Path("accepted-calibration.invalid.json")
    lifecycle = CalibrationPersistenceLifecycle(
        _RecordingProvisioner(calls),
        _RecordingStore(
            calls,
            loaded=CalibrationLoadResult(None, "checksum invalid", backup),
        ),
        _policy(),
    )

    result = lifecycle.recover_once()

    assert result.status is CalibrationPersistenceStatus.FAULTED
    assert result.recovered_from == backup
    assert calls[-1] == ("configure", None)


def test_real_provisioner_recovery_still_has_no_executor_dependency() -> None:
    diagnostics = CursorDiagnosticsController()
    provisioner = CursorPipelineProvisioner(diagnostics, _GeometryProvider())
    lifecycle = CalibrationPersistenceLifecycle(
        provisioner,
        _RecordingStore(
            [],
            loaded=CalibrationLoadResult(_accepted(), provenance=_provenance()),
        ),
        _policy(),
    )

    result = lifecycle.recover_once()

    assert result.status is CalibrationPersistenceStatus.RECOVERED
    assert result.provisioning is not None
    assert result.provisioning.status is CursorProvisioningStatus.READY


def test_recovery_clears_when_current_display_geometry_changed() -> None:
    calls: list[object] = []
    accepted = _accepted()
    current = PhysicalScreenGeometry(0, 0, 2560, 1440)
    lifecycle = CalibrationPersistenceLifecycle(
        _RecordingProvisioner(calls, geometry=current),
        _RecordingStore(
            calls,
            loaded=CalibrationLoadResult(accepted, provenance=_provenance()),
        ),
        _policy(),
    )

    result = lifecycle.recover_once()

    assert result.status is CalibrationPersistenceStatus.INCOMPATIBLE
    assert "differs" in result.message
    assert calls == [
        ("load", _policy()),
        ("configure", accepted),
        ("configure", None),
    ]
