"""Fake-only composition of accepted calibration and dormant cursor-domain stages."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from meyes.calibration.acceptance import AcceptedCalibration
from meyes.calibration.mapper import NormalizedScreenPoint
from meyes.cursor.gate import CursorGateSnapshot, CursorMovementGate
from meyes.cursor.screen_mapping import ScreenCoordinateMapper, ScreenMappingResult
from meyes.cursor.smoothing import OneEuroPointFilter
from meyes.domain.events import GestureEvent
from meyes.domain.observations import GazeFeatureObservation, GazeFeatureVector


class CursorPipelineStatus(StrEnum):
    FEATURE_UNAVAILABLE = "feature_unavailable"
    GATE_BLOCKED = "gate_blocked"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class CursorPipelineResult:
    status: CursorPipelineStatus
    gate: CursorGateSnapshot
    normalized: NormalizedScreenPoint | None = None
    screen: ScreenMappingResult | None = None


class CursorPipeline:
    """Produce inspectable pixel candidates without owning or calling an input executor."""

    def __init__(
        self,
        calibration: AcceptedCalibration,
        screen_mapper: ScreenCoordinateMapper,
        *,
        smoother: OneEuroPointFilter | None = None,
        gate: CursorMovementGate | None = None,
    ) -> None:
        if not isinstance(calibration, AcceptedCalibration):
            raise TypeError("Expected AcceptedCalibration")
        if not isinstance(screen_mapper, ScreenCoordinateMapper):
            raise TypeError("Expected ScreenCoordinateMapper")
        if smoother is not None and not isinstance(smoother, OneEuroPointFilter):
            raise TypeError("Expected OneEuroPointFilter or None")
        if gate is not None and not isinstance(gate, CursorMovementGate):
            raise TypeError("Expected CursorMovementGate or None")
        self._calibration = calibration
        self._screen_mapper = screen_mapper
        self._smoother = smoother or OneEuroPointFilter()
        self._gate = gate or CursorMovementGate()

    @property
    def gate_snapshot(self) -> CursorGateSnapshot:
        return self._gate.snapshot

    def update(self, observation: GazeFeatureObservation) -> CursorPipelineResult:
        if not isinstance(observation, GazeFeatureObservation):
            raise TypeError("Expected GazeFeatureObservation")
        gate = self._gate.poll(observation.capture_timestamp)
        if not observation.ready or not isinstance(observation.combined, GazeFeatureVector):
            self._smoother.reset()
            return CursorPipelineResult(CursorPipelineStatus.FEATURE_UNAVAILABLE, gate)
        if not gate.movement_allowed:
            self._smoother.reset()
            return CursorPipelineResult(CursorPipelineStatus.GATE_BLOCKED, gate)
        predicted = self._calibration.fit_result.mapper.predict(observation.combined)
        smoothed = self._smoother.update(predicted, timestamp=observation.capture_timestamp)
        mapped = self._screen_mapper.map(smoothed)
        return CursorPipelineResult(CursorPipelineStatus.READY, gate, smoothed, mapped)

    def handle_event(self, event: GestureEvent) -> CursorGateSnapshot:
        snapshot = self._gate.handle_event(event)
        if not snapshot.movement_allowed:
            self._smoother.reset()
        return snapshot

    def suspend(self, timestamp: float) -> CursorGateSnapshot:
        self._smoother.reset()
        return self._gate.suspend(timestamp)

    def resume_tracking(self, timestamp: float) -> CursorGateSnapshot:
        self._smoother.reset()
        return self._gate.resume_tracking(timestamp)

    def poll(self, timestamp: float) -> CursorGateSnapshot:
        snapshot = self._gate.poll(timestamp)
        if not snapshot.movement_allowed:
            self._smoother.reset()
        return snapshot

    def reset(self) -> CursorGateSnapshot:
        self._smoother.reset()
        return self._gate.reset()
