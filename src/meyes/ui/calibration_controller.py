"""Qt-owned orchestration for volatile calibration collection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QObject, Signal, Slot

from meyes.calibration.acceptance import (
    AcceptedCalibration,
    CalibrationAcceptance,
    CalibrationAcceptancePolicy,
    CalibrationAcceptanceState,
    evaluate_calibration_acceptance,
    review_required_acceptance,
)
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
    acceptance: CalibrationAcceptance | None = None


class CalibrationController(QObject):
    """Serialize gaze features into one bounded calibration session."""

    snapshot_changed = Signal(object)
    capture_decided = Signal(object)
    fit_changed = Signal(object)

    def __init__(
        self,
        session: CalibrationSession | None = None,
        parent: QObject | None = None,
        *,
        acceptance_policy: CalibrationAcceptancePolicy | None = None,
    ) -> None:
        super().__init__(parent)
        if acceptance_policy is not None and not isinstance(
            acceptance_policy, CalibrationAcceptancePolicy
        ):
            raise TypeError("Expected CalibrationAcceptancePolicy or None")
        self._session = session or CalibrationSession()
        self._acceptance_policy = acceptance_policy
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

    @property
    def accepted_fit_result(self) -> CalibrationFitResult | None:
        acceptance = self._fit_outcome.acceptance
        if acceptance is None or acceptance.state is not CalibrationAcceptanceState.ACCEPTED:
            return None
        return self._fit_result

    @property
    def accepted_calibration(self) -> AcceptedCalibration | None:
        fit_result = self.accepted_fit_result
        acceptance = self._fit_outcome.acceptance
        if fit_result is None or acceptance is None:
            return None
        return AcceptedCalibration(fit_result, acceptance)

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
            acceptance = (
                review_required_acceptance()
                if self._acceptance_policy is None
                else evaluate_calibration_acceptance(
                    self._acceptance_policy,
                    result.validation,
                )
            )
            self._fit_result = result
            self._fit_outcome = CalibrationFitOutcome(
                CalibrationFitState.READY,
                _acceptance_message(acceptance),
                validation=result.validation,
                acceptance=acceptance,
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


def _acceptance_message(acceptance: CalibrationAcceptance) -> str:
    if acceptance.state is CalibrationAcceptanceState.ACCEPTED:
        return (
            "Mapper meets every configured acceptance limit. "
            "Pointer output still requires explicit Live Input consent."
        )
    if acceptance.state is CalibrationAcceptanceState.REJECTED:
        return (
            "Volatile mapper missed configured acceptance limits: "
            f"{'; '.join(acceptance.reasons)}. Retry collection."
        )
    return (
        "Volatile mapper fitted, but no complete evidence-backed acceptance policy is "
        "configured. Review is required and pointer output remains off."
    )
