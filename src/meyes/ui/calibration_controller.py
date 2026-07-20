"""Qt-owned orchestration for volatile calibration collection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QObject, Signal, Slot

from meyes.calibration.mapper import (
    CalibrationFitResult,
    CalibrationValidation,
    fit_and_validate_polynomial_mapper,
)
from meyes.calibration.session import (
    CalibrationCaptureResult,
    CalibrationSession,
    CalibrationSessionState,
    CalibrationSnapshot,
)
from meyes.domain.observations import GazeFeatureObservation


class CalibrationFitState(StrEnum):
    """Availability of the volatile fitted mapper."""

    NONE = "none"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CalibrationFitOutcome:
    """UI-safe fit state without persisting or activating a mapper."""

    state: CalibrationFitState
    message: str
    validation: CalibrationValidation | None = None


class CalibrationController(QObject):
    """Serialize gaze features into one bounded calibration session."""

    snapshot_changed = Signal(object)
    capture_decided = Signal(object)
    fit_changed = Signal(object)

    def __init__(
        self,
        session: CalibrationSession | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session or CalibrationSession()
        self._fit_result: CalibrationFitResult | None = None
        self._fit_outcome = CalibrationFitOutcome(
            CalibrationFitState.NONE,
            "No volatile calibration mapper is fitted.",
        )

    @property
    def snapshot(self) -> CalibrationSnapshot:
        return self._session.snapshot

    @property
    def fit_result(self) -> CalibrationFitResult | None:
        return self._fit_result

    @property
    def fit_outcome(self) -> CalibrationFitOutcome:
        return self._fit_outcome

    def start(self) -> CalibrationSnapshot:
        self._clear_fit()
        return self._publish(self._session.start())

    def begin_target(self) -> CalibrationSnapshot:
        return self._publish(self._session.begin_target())

    def advance(self) -> CalibrationSnapshot:
        snapshot = self._publish(self._session.advance())
        if snapshot.state is CalibrationSessionState.COMPLETE:
            self._fit_complete_session()
        return snapshot

    def cancel(self) -> CalibrationSnapshot:
        self._clear_fit()
        return self._publish(self._session.cancel())

    def reset(self) -> CalibrationSnapshot:
        self._clear_fit()
        return self._publish(self._session.reset())

    @Slot(object)
    def observe_feature(self, payload: object) -> None:
        if self._session.snapshot.state is not CalibrationSessionState.COLLECTING:
            return
        if not isinstance(payload, GazeFeatureObservation):
            raise TypeError("Expected GazeFeatureObservation")
        result = self._session.add_feature(payload)
        self.capture_decided.emit(result)
        self.snapshot_changed.emit(result.snapshot)

    def _publish(self, snapshot: CalibrationSnapshot) -> CalibrationSnapshot:
        self.snapshot_changed.emit(snapshot)
        return snapshot

    def _fit_complete_session(self) -> None:
        try:
            result = fit_and_validate_polynomial_mapper(self._session.samples)
        except (TypeError, ValueError, RuntimeError):
            self._fit_result = None
            self._fit_outcome = CalibrationFitOutcome(
                CalibrationFitState.FAILED,
                "The collected feature geometry could not produce a stable mapper. "
                "Retry collection.",
            )
        else:
            self._fit_result = result
            self._fit_outcome = CalibrationFitOutcome(
                CalibrationFitState.READY,
                "Volatile mapper fitted and held-out metrics calculated. "
                "Pointer output remains off.",
                validation=result.validation,
            )
        self.fit_changed.emit(self._fit_outcome)

    def _clear_fit(self) -> None:
        self._fit_result = None
        self._fit_outcome = CalibrationFitOutcome(
            CalibrationFitState.NONE,
            "No volatile calibration mapper is fitted.",
        )
        self.fit_changed.emit(self._fit_outcome)


def calibration_snapshot(value: object) -> CalibrationSnapshot:
    if not isinstance(value, CalibrationSnapshot):
        raise TypeError("Expected CalibrationSnapshot")
    return value


def calibration_capture_result(value: object) -> CalibrationCaptureResult:
    if not isinstance(value, CalibrationCaptureResult):
        raise TypeError("Expected CalibrationCaptureResult")
    return value


def calibration_fit_outcome(value: object) -> CalibrationFitOutcome:
    if not isinstance(value, CalibrationFitOutcome):
        raise TypeError("Expected CalibrationFitOutcome")
    return value
