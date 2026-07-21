"""Fail-closed construction of the calibrated production cursor pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from meyes.calibration.acceptance import AcceptedCalibration
from meyes.cursor.gate import CursorGateSettings, CursorMovementGate
from meyes.cursor.pipeline import CursorPipeline
from meyes.cursor.screen_mapping import (
    PhysicalScreenGeometry,
    PhysicalScreenGeometryProvider,
    PrimaryScreenMapper,
)
from meyes.cursor.smoothing import OneEuroFilterSettings, OneEuroPointFilter
from meyes.ui.cursor_diagnostics import CursorDiagnosticsController


class CursorProvisioningStatus(StrEnum):
    UNAVAILABLE = "unavailable"
    READY = "ready"
    FAULTED = "faulted"


@dataclass(frozen=True, slots=True)
class CursorProvisioningResult:
    status: CursorProvisioningStatus
    message: str
    geometry: PhysicalScreenGeometry | None = None


class CursorPipelineProvisioner:
    """Install a candidate pipeline only from accepted calibration plus geometry."""

    def __init__(
        self,
        diagnostics: CursorDiagnosticsController,
        geometry_provider: PhysicalScreenGeometryProvider | None,
        *,
        filter_settings: OneEuroFilterSettings | None = None,
        gate_settings: CursorGateSettings | None = None,
    ) -> None:
        if not isinstance(diagnostics, CursorDiagnosticsController):
            raise TypeError("Expected CursorDiagnosticsController")
        if geometry_provider is not None and not isinstance(
            geometry_provider, PhysicalScreenGeometryProvider
        ):
            raise TypeError("Expected PhysicalScreenGeometryProvider or None")
        if filter_settings is not None and not isinstance(filter_settings, OneEuroFilterSettings):
            raise TypeError("Expected OneEuroFilterSettings or None")
        if gate_settings is not None and not isinstance(gate_settings, CursorGateSettings):
            raise TypeError("Expected CursorGateSettings or None")
        self._diagnostics = diagnostics
        self._geometry_provider = geometry_provider
        self._filter_settings = filter_settings or OneEuroFilterSettings()
        self._gate_settings = gate_settings or CursorGateSettings()
        self._active_geometry: PhysicalScreenGeometry | None = None

    @property
    def active_geometry(self) -> PhysicalScreenGeometry | None:
        """Return the exact geometry used by the currently provisioned pipeline."""

        return self._active_geometry

    def configure(
        self,
        calibration: AcceptedCalibration | None,
    ) -> CursorProvisioningResult:
        if calibration is not None and not isinstance(calibration, AcceptedCalibration):
            raise TypeError("Expected AcceptedCalibration or None")
        self._active_geometry = None
        if calibration is None:
            message = "Cursor diagnostics requires an accepted calibration."
            self._diagnostics.set_unavailable(message)
            return CursorProvisioningResult(CursorProvisioningStatus.UNAVAILABLE, message)
        if self._geometry_provider is None:
            message = "Physical-screen geometry is unavailable on this platform."
            self._diagnostics.set_unavailable(message)
            return CursorProvisioningResult(CursorProvisioningStatus.UNAVAILABLE, message)
        try:
            geometry = self._geometry_provider.read()
            if not isinstance(geometry, PhysicalScreenGeometry):
                raise TypeError("Geometry provider returned an invalid result")
            pipeline = CursorPipeline(
                calibration,
                PrimaryScreenMapper(geometry),
                smoother=OneEuroPointFilter(self._filter_settings),
                gate=CursorMovementGate(self._gate_settings),
            )
        except (OSError, TypeError, ValueError, RuntimeError):
            message = "Physical-screen geometry could not be read safely."
            self._diagnostics.set_unavailable(message)
            return CursorProvisioningResult(CursorProvisioningStatus.FAULTED, message)
        self._diagnostics.set_pipeline(pipeline)
        self._active_geometry = geometry
        return CursorProvisioningResult(
            CursorProvisioningStatus.READY,
            "Cursor pipeline is configured; OS output still requires an armed Live Input session.",
            geometry,
        )

    def read(self) -> PhysicalScreenGeometry:
        """Revalidate and return geometry for one native pointer movement."""

        expected = self._active_geometry
        provider = self._geometry_provider
        if expected is None or provider is None:
            raise RuntimeError("No accepted display geometry is active")
        try:
            current = provider.read()
            if not isinstance(current, PhysicalScreenGeometry):
                raise TypeError("Geometry provider returned an invalid result")
        except (OSError, TypeError, ValueError, RuntimeError):
            self._invalidate_execution_geometry(
                "Current physical-screen geometry could not be verified safely."
            )
            raise RuntimeError("Current display geometry could not be verified") from None
        if current != expected:
            self._invalidate_execution_geometry(
                "Physical-screen geometry changed; recalibration is required."
            )
            raise RuntimeError("Current display geometry does not match accepted calibration")
        return expected

    def _invalidate_execution_geometry(self, message: str) -> None:
        self._active_geometry = None
        self._diagnostics.set_unavailable(message)
