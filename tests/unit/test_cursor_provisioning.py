from __future__ import annotations

from dataclasses import dataclass, field

from pytestqt.qtbot import QtBot

from meyes.calibration.acceptance import (
    AcceptedCalibration,
    CalibrationAcceptance,
    CalibrationAcceptanceState,
)
from meyes.calibration.mapper import (
    CalibrationFitResult,
    CalibrationValidation,
    PolynomialCalibrationMapper,
)
from meyes.cursor.screen_mapping import PhysicalScreenGeometry
from meyes.domain.observations import (
    GazeFeatureObservation,
    GazeFeatureStatus,
    GazeFeatureVector,
)
from meyes.ui.cursor_diagnostics import CursorDiagnosticsController, CursorDiagnosticsStatus
from meyes.ui.cursor_provisioning import CursorPipelineProvisioner, CursorProvisioningStatus


@dataclass
class _GeometryProvider:
    geometry: PhysicalScreenGeometry = field(
        default_factory=lambda: PhysicalScreenGeometry(0, 0, 1920, 1080)
    )
    error: Exception | None = None
    reads: int = 0

    def read(self) -> PhysicalScreenGeometry:
        self.reads += 1
        if self.error is not None:
            raise self.error
        return self.geometry


@dataclass
class _Clock:
    value: float = 1.0

    def __call__(self) -> float:
        return self.value


def _accepted_calibration() -> AcceptedCalibration:
    mapper = PolynomialCalibrationMapper(
        (0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    )
    fit = CalibrationFitResult(mapper, CalibrationValidation(18, 0.01, 0.01, 0.02))
    return AcceptedCalibration(
        fit,
        CalibrationAcceptance(CalibrationAcceptanceState.ACCEPTED),
    )


def _observation() -> GazeFeatureObservation:
    vector = GazeFeatureVector(0.5, 0.5)
    return GazeFeatureObservation(
        1,
        1.0,
        1.001,
        GazeFeatureStatus.READY,
        vector,
        vector,
        vector,
    )


def test_missing_acceptance_never_reads_geometry(qtbot: QtBot) -> None:
    diagnostics = CursorDiagnosticsController()
    provider = _GeometryProvider()
    provisioner = CursorPipelineProvisioner(diagnostics, provider)

    result = provisioner.configure(None)
    diagnostics.start()

    assert result.status is CursorProvisioningStatus.UNAVAILABLE
    assert provider.reads == 0
    assert diagnostics.snapshot.status is CursorDiagnosticsStatus.UNAVAILABLE
    assert diagnostics.snapshot.message == result.message
    diagnostics.close()


def test_accepted_calibration_configures_fake_only_candidate_pipeline(qtbot: QtBot) -> None:
    clock = _Clock()
    diagnostics = CursorDiagnosticsController(clock=clock)
    provider = _GeometryProvider()
    provisioner = CursorPipelineProvisioner(diagnostics, provider)

    result = provisioner.configure(_accepted_calibration())
    diagnostics.start()
    clock.value = 1.12
    diagnostics.poll()
    diagnostics.observe_feature(_observation())

    assert result.status is CursorProvisioningStatus.READY
    assert result.geometry == provider.geometry
    assert provider.reads == 1
    assert diagnostics.snapshot.status is CursorDiagnosticsStatus.READY
    assert diagnostics.snapshot.pixel_x == 960
    assert diagnostics.snapshot.pixel_y == 540
    assert "no operating-system output" in diagnostics.snapshot.message
    diagnostics.close()


def test_native_geometry_fault_clears_previously_configured_pipeline(qtbot: QtBot) -> None:
    clock = _Clock()
    diagnostics = CursorDiagnosticsController(clock=clock)
    provider = _GeometryProvider()
    provisioner = CursorPipelineProvisioner(diagnostics, provider)
    accepted = _accepted_calibration()
    provisioner.configure(accepted)
    diagnostics.start()
    clock.value = 1.12
    diagnostics.poll()
    diagnostics.observe_feature(_observation())
    ready_snapshot = diagnostics.snapshot
    assert ready_snapshot.status is CursorDiagnosticsStatus.READY
    provider.error = OSError("native read failed")

    result = provisioner.configure(accepted)
    diagnostics.start()
    fault_snapshot = diagnostics.snapshot

    assert result.status is CursorProvisioningStatus.FAULTED
    assert fault_snapshot.status is CursorDiagnosticsStatus.UNAVAILABLE
    assert fault_snapshot.pixel_x is None
    assert fault_snapshot.message == result.message
    diagnostics.close()


def test_accepted_calibration_stays_unavailable_without_platform_provider(qtbot: QtBot) -> None:
    diagnostics = CursorDiagnosticsController()
    provisioner = CursorPipelineProvisioner(diagnostics, None)

    result = provisioner.configure(_accepted_calibration())

    assert result.status is CursorProvisioningStatus.UNAVAILABLE
    assert "unavailable on this platform" in result.message


def test_rejects_incomplete_geometry_provider(qtbot: QtBot) -> None:
    diagnostics = CursorDiagnosticsController()

    try:
        CursorPipelineProvisioner(diagnostics, object())  # type: ignore[arg-type]
    except TypeError as error:
        assert "PhysicalScreenGeometryProvider" in str(error)
    else:
        raise AssertionError("Incomplete provider should be rejected")
