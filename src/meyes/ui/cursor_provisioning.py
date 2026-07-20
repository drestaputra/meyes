"""Fail-closed construction of the fake-only production diagnostics pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from meyes.calibration.acceptance import AcceptedCalibration
from meyes.cursor.pipeline import CursorPipeline
from meyes.cursor.screen_mapping import (
    PhysicalScreenGeometry,
    PhysicalScreenGeometryProvider,
    PrimaryScreenMapper,
)
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
    """Install no-executor diagnostics only from accepted calibration plus geometry."""

    def __init__(
        self,
        diagnostics: CursorDiagnosticsController,
        geometry_provider: PhysicalScreenGeometryProvider | None,
    ) -> None:
        if not isinstance(diagnostics, CursorDiagnosticsController):
            raise TypeError("Expected CursorDiagnosticsController")
        if geometry_provider is not None and not isinstance(
            geometry_provider, PhysicalScreenGeometryProvider
        ):
            raise TypeError("Expected PhysicalScreenGeometryProvider or None")
        self._diagnostics = diagnostics
        self._geometry_provider = geometry_provider

    def configure(
        self,
        calibration: AcceptedCalibration | None,
    ) -> CursorProvisioningResult:
        if calibration is not None and not isinstance(calibration, AcceptedCalibration):
            raise TypeError("Expected AcceptedCalibration or None")
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
            pipeline = CursorPipeline(calibration, PrimaryScreenMapper(geometry))
        except (OSError, TypeError, ValueError, RuntimeError):
            message = "Physical-screen geometry could not be read safely."
            self._diagnostics.set_unavailable(message)
            return CursorProvisioningResult(CursorProvisioningStatus.FAULTED, message)
        self._diagnostics.set_pipeline(pipeline)
        return CursorProvisioningResult(
            CursorProvisioningStatus.READY,
            "Fake-only cursor diagnostics pipeline is configured; OS output remains disconnected.",
            geometry,
        )
