from __future__ import annotations

from dataclasses import dataclass, field

import pytest
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
from meyes.cursor.gate import CursorGateSettings
from meyes.cursor.screen_mapping import PhysicalScreenGeometry
from meyes.cursor.smoothing import OneEuroFilterSettings
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


def _observation_at(sequence: int, capture: float, x: float, y: float) -> GazeFeatureObservation:
    vector = GazeFeatureVector(x, y)
    return GazeFeatureObservation(
        sequence,
        capture,
        capture + 0.001,
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
    assert "armed Live Input" in diagnostics.snapshot.message
    diagnostics.close()


def test_execution_geometry_requires_active_matching_provisioning(qtbot: QtBot) -> None:
    diagnostics = CursorDiagnosticsController()
    provider = _GeometryProvider()
    provisioner = CursorPipelineProvisioner(diagnostics, provider)

    with pytest.raises(RuntimeError, match="No accepted display geometry"):
        provisioner.read()

    configured = provisioner.configure(_accepted_calibration())
    assert configured.status is CursorProvisioningStatus.READY
    assert configured.geometry == provider.geometry
    assert provisioner.read() == provider.geometry
    assert provider.reads == 2

    provider.geometry = PhysicalScreenGeometry(0, 0, 2560, 1440)
    with pytest.raises(RuntimeError, match="does not match accepted calibration"):
        provisioner.read()

    assert provisioner.active_geometry is None
    assert diagnostics.snapshot.status is CursorDiagnosticsStatus.UNAVAILABLE
    assert "recalibration is required" in diagnostics.snapshot.message


def test_execution_geometry_native_failure_invalidates_pipeline(qtbot: QtBot) -> None:
    diagnostics = CursorDiagnosticsController()
    provider = _GeometryProvider()
    provisioner = CursorPipelineProvisioner(diagnostics, provider)
    provisioner.configure(_accepted_calibration())
    provider.error = OSError("display disconnected")

    with pytest.raises(RuntimeError, match="could not be verified"):
        provisioner.read()

    assert provisioner.active_geometry is None
    assert diagnostics.snapshot.status is CursorDiagnosticsStatus.UNAVAILABLE


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


def test_configured_resume_delay_controls_fake_pipeline_gate(qtbot: QtBot) -> None:
    clock = _Clock()
    diagnostics = CursorDiagnosticsController(clock=clock)
    provisioner = CursorPipelineProvisioner(
        diagnostics,
        _GeometryProvider(),
        gate_settings=CursorGateSettings(resume_delay_seconds=0.5),
    )
    provisioner.configure(_accepted_calibration())
    diagnostics.start()
    clock.value = 1.49
    diagnostics.poll()
    diagnostics.observe_feature(_observation())
    blocked_snapshot = diagnostics.snapshot

    assert blocked_snapshot.status is CursorDiagnosticsStatus.BLOCKED

    clock.value = 1.5
    diagnostics.poll()
    diagnostics.observe_feature(_observation_at(2, 1.1, 0.5, 0.5))
    ready_snapshot = diagnostics.snapshot

    assert ready_snapshot.status is CursorDiagnosticsStatus.READY
    diagnostics.close()


def test_configured_filter_changes_fake_candidate_response(qtbot: QtBot) -> None:
    clock = _Clock()
    diagnostics = CursorDiagnosticsController(clock=clock)
    provisioner = CursorPipelineProvisioner(
        diagnostics,
        _GeometryProvider(),
        filter_settings=OneEuroFilterSettings(
            minimum_cutoff=0.1,
            speed_coefficient=0.0,
            derivative_cutoff=1.0,
            maximum_gap_seconds=1.0,
        ),
        gate_settings=CursorGateSettings(resume_delay_seconds=0.0),
    )
    provisioner.configure(_accepted_calibration())
    diagnostics.start()
    diagnostics.poll()
    diagnostics.observe_feature(_observation_at(1, 0.9, 0.0, 0.5))
    clock.value = 1.1
    diagnostics.observe_feature(_observation_at(2, 1.0, 1.0, 0.5))

    assert diagnostics.snapshot.status is CursorDiagnosticsStatus.READY
    assert diagnostics.snapshot.pixel_x is not None
    assert diagnostics.snapshot.pixel_x < 300
    diagnostics.close()


def test_settings_update_without_calibration_never_reads_geometry(qtbot: QtBot) -> None:
    diagnostics = CursorDiagnosticsController()
    provider = _GeometryProvider()
    provisioner = CursorPipelineProvisioner(diagnostics, provider)
    filter_settings = OneEuroFilterSettings(minimum_cutoff=2.0)
    gate_settings = CursorGateSettings(resume_delay_seconds=0.4)

    result = provisioner.update_settings(filter_settings, gate_settings)

    assert result.status is CursorProvisioningStatus.UNAVAILABLE
    assert provisioner.filter_settings == filter_settings
    assert provisioner.gate_settings == gate_settings
    assert provider.reads == 0


def test_settings_update_rebuilds_only_active_accepted_pipeline(qtbot: QtBot) -> None:
    diagnostics = CursorDiagnosticsController()
    provider = _GeometryProvider()
    provisioner = CursorPipelineProvisioner(diagnostics, provider)
    provisioner.configure(_accepted_calibration())
    filter_settings = OneEuroFilterSettings(speed_coefficient=0.2)
    gate_settings = CursorGateSettings(resume_delay_seconds=0.4)

    result = provisioner.update_settings(filter_settings, gate_settings)

    assert result.status is CursorProvisioningStatus.READY
    assert provisioner.filter_settings == filter_settings
    assert provisioner.gate_settings == gate_settings
    assert provider.reads == 2


def test_display_mismatch_prevents_settings_from_resurrecting_pipeline(qtbot: QtBot) -> None:
    diagnostics = CursorDiagnosticsController()
    provider = _GeometryProvider()
    provisioner = CursorPipelineProvisioner(diagnostics, provider)
    provisioner.configure(_accepted_calibration())
    provider.geometry = PhysicalScreenGeometry(0, 0, 2560, 1440)

    result = provisioner.update_settings(
        OneEuroFilterSettings(minimum_cutoff=2.0),
        CursorGateSettings(resume_delay_seconds=0.4),
    )

    assert result.status is CursorProvisioningStatus.FAULTED
    assert "recalibration is required" in result.message
    assert provider.reads == 2
    assert provisioner.active_geometry is None

    second_result = provisioner.update_settings(
        OneEuroFilterSettings(minimum_cutoff=3.0),
        CursorGateSettings(resume_delay_seconds=0.5),
    )
    assert second_result.status is CursorProvisioningStatus.UNAVAILABLE
    assert provider.reads == 2
