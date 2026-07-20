"""Qt-owned orchestration for volatile calibration collection."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from meyes.calibration.session import (
    CalibrationCaptureResult,
    CalibrationSession,
    CalibrationSessionState,
    CalibrationSnapshot,
)
from meyes.domain.observations import GazeFeatureObservation


class CalibrationController(QObject):
    """Serialize gaze features into one bounded calibration session."""

    snapshot_changed = Signal(object)
    capture_decided = Signal(object)

    def __init__(
        self,
        session: CalibrationSession | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session or CalibrationSession()

    @property
    def snapshot(self) -> CalibrationSnapshot:
        return self._session.snapshot

    def start(self) -> CalibrationSnapshot:
        return self._publish(self._session.start())

    def begin_target(self) -> CalibrationSnapshot:
        return self._publish(self._session.begin_target())

    def advance(self) -> CalibrationSnapshot:
        return self._publish(self._session.advance())

    def cancel(self) -> CalibrationSnapshot:
        return self._publish(self._session.cancel())

    def reset(self) -> CalibrationSnapshot:
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


def calibration_snapshot(value: object) -> CalibrationSnapshot:
    if not isinstance(value, CalibrationSnapshot):
        raise TypeError("Expected CalibrationSnapshot")
    return value


def calibration_capture_result(value: object) -> CalibrationCaptureResult:
    if not isinstance(value, CalibrationCaptureResult):
        raise TypeError("Expected CalibrationCaptureResult")
    return value
