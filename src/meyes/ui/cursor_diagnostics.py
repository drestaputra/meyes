"""Qt-owned, fake-only cursor candidate diagnostics with freshness expiry."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from meyes.cursor.gate import CursorGateState
from meyes.cursor.pipeline import CursorPipeline, CursorPipelineResult, CursorPipelineStatus
from meyes.domain.events import GestureEvent
from meyes.domain.observations import GazeFeatureObservation

_DEFAULT_UNAVAILABLE_MESSAGE = "No accepted calibration and physical-screen pipeline is configured."


class CursorDiagnosticsStatus(StrEnum):
    UNAVAILABLE = "unavailable"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"
    READY = "ready"
    STALE = "stale"
    FAULTED = "faulted"


@dataclass(frozen=True, slots=True)
class CursorDiagnosticsSnapshot:
    status: CursorDiagnosticsStatus
    message: str
    gate_state: CursorGateState | None = None
    normalized_x: float | None = None
    normalized_y: float | None = None
    pixel_x: int | None = None
    pixel_y: int | None = None
    clamped: bool = False


class CursorDiagnosticsController(QObject):
    """Own fake-only pipeline timing without accepting an input executor."""

    snapshot_changed = Signal(object)

    def __init__(
        self,
        pipeline: CursorPipeline | None = None,
        parent: QObject | None = None,
        *,
        freshness_timeout: float = 0.25,
        clock: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(parent)
        if pipeline is not None and not isinstance(pipeline, CursorPipeline):
            raise TypeError("Expected CursorPipeline or None")
        if not _positive_finite(freshness_timeout):
            raise ValueError("Cursor freshness timeout must be finite and positive")
        self._pipeline = pipeline
        self._freshness_timeout = float(freshness_timeout)
        self._clock = clock or time.monotonic
        self._tracking_available = False
        self._last_received_at: float | None = None
        self._snapshot = CursorDiagnosticsSnapshot(
            CursorDiagnosticsStatus.UNAVAILABLE,
            _DEFAULT_UNAVAILABLE_MESSAGE,
        )
        self._unavailable_message = _DEFAULT_UNAVAILABLE_MESSAGE
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(max(5, min(25, round(freshness_timeout * 100))))
        self._watchdog.timeout.connect(self.poll)

    @property
    def snapshot(self) -> CursorDiagnosticsSnapshot:
        return self._snapshot

    def set_pipeline(
        self,
        pipeline: CursorPipeline | None,
        *,
        unavailable_message: str = _DEFAULT_UNAVAILABLE_MESSAGE,
    ) -> CursorDiagnosticsSnapshot:
        if pipeline is not None and not isinstance(pipeline, CursorPipeline):
            raise TypeError("Expected CursorPipeline or None")
        if not isinstance(unavailable_message, str) or not unavailable_message.strip():
            raise ValueError("Unavailable message must be a non-empty string")
        if self._pipeline is not None:
            self._pipeline.reset()
        self._pipeline = pipeline
        self._unavailable_message = (
            unavailable_message.strip() if pipeline is None else _DEFAULT_UNAVAILABLE_MESSAGE
        )
        self._last_received_at = None
        if pipeline is None:
            return self._publish(
                CursorDiagnosticsStatus.UNAVAILABLE,
                self._unavailable_message,
            )
        if self._tracking_available:
            pipeline.resume_tracking(self._now())
            return self._publish_result_state("Waiting for a fresh gaze feature.")
        return self._publish(CursorDiagnosticsStatus.SUSPENDED, "Tracking is suspended.")

    def set_unavailable(self, message: str) -> CursorDiagnosticsSnapshot:
        """Remove any pipeline and retain an honest unavailable reason."""

        return self.set_pipeline(None, unavailable_message=message)

    @Slot()
    def start(self) -> None:
        self._tracking_available = True
        self._last_received_at = None
        if not self._watchdog.isActive():
            self._watchdog.start()
        if self._pipeline is None:
            self._publish(
                CursorDiagnosticsStatus.UNAVAILABLE,
                self._unavailable_message,
            )
            return
        self._pipeline.resume_tracking(self._now())
        self._publish_result_state("Waiting for a fresh gaze feature.")

    @Slot()
    def suspend(self) -> None:
        self._tracking_available = False
        self._last_received_at = None
        self._watchdog.stop()
        if self._pipeline is not None:
            self._pipeline.suspend(self._now())
        self._publish(CursorDiagnosticsStatus.SUSPENDED, "Tracking is suspended.")

    @Slot(object)
    def observe_feature(self, payload: object) -> None:
        if not isinstance(payload, GazeFeatureObservation):
            raise TypeError("Expected GazeFeatureObservation")
        if self._pipeline is None:
            return
        if not self._tracking_available:
            self._publish(CursorDiagnosticsStatus.SUSPENDED, "Tracking is suspended.")
            return
        now = self._now()
        if self._snapshot.status is CursorDiagnosticsStatus.STALE:
            self._pipeline.resume_tracking(now)
        self._last_received_at = now
        try:
            result = self._pipeline.update(payload, gate_timestamp=now)
        except (TypeError, ValueError, RuntimeError):
            self._pipeline.suspend(now)
            self._publish(
                CursorDiagnosticsStatus.FAULTED,
                "Cursor candidate pipeline rejected the latest feature.",
            )
            return
        self._publish_pipeline_result(result)

    @Slot(object)
    def handle_event(self, payload: object) -> None:
        if not isinstance(payload, GestureEvent):
            raise TypeError("Expected GestureEvent")
        if self._pipeline is None or not self._tracking_available:
            return
        delivered = GestureEvent(
            payload.type,
            self._now(),
            payload.source_sequence,
            payload.duration_ms,
        )
        try:
            gate = self._pipeline.handle_event(delivered)
        except (TypeError, ValueError, RuntimeError):
            self._pipeline.suspend(self._now())
            self._publish(CursorDiagnosticsStatus.FAULTED, "Cursor gate rejected an event.")
            return
        if not gate.movement_allowed:
            self._publish(
                CursorDiagnosticsStatus.BLOCKED,
                f"Cursor candidate blocked: {gate.state.value.replace('_', ' ')}.",
                gate_state=gate.state,
            )

    @Slot()
    def clear_feature(self) -> None:
        self._last_received_at = None
        if self._pipeline is None:
            return
        if not self._tracking_available:
            self._publish(CursorDiagnosticsStatus.SUSPENDED, "Tracking is suspended.")
            return
        self._pipeline.suspend(self._now())
        self._publish(CursorDiagnosticsStatus.STALE, "Gaze feature expired or was cleared.")

    @Slot()
    def poll(self) -> None:
        if self._pipeline is None or not self._tracking_available:
            return
        now = self._now()
        if (
            self._last_received_at is not None
            and now - self._last_received_at > self._freshness_timeout
        ):
            self.clear_feature()
            return
        try:
            gate = self._pipeline.poll(now)
        except (TypeError, ValueError, RuntimeError):
            self._pipeline.suspend(now)
            self._publish(CursorDiagnosticsStatus.FAULTED, "Cursor gate polling failed.")
            return
        if self._snapshot.status is CursorDiagnosticsStatus.BLOCKED and gate.movement_allowed:
            self._publish(
                CursorDiagnosticsStatus.BLOCKED,
                "Cursor gate reopened; waiting for a fresh gaze feature.",
                gate_state=gate.state,
            )

    def close(self) -> None:
        self.suspend()
        if self._pipeline is not None:
            self._pipeline.reset()

    def _publish_pipeline_result(self, result: CursorPipelineResult) -> None:
        if result.status is CursorPipelineStatus.READY:
            assert result.normalized is not None and result.screen is not None
            self._publish(
                CursorDiagnosticsStatus.READY,
                "Fake-only cursor candidate ready; no operating-system output was sent.",
                gate_state=result.gate.state,
                normalized_x=result.normalized.x,
                normalized_y=result.normalized.y,
                pixel_x=result.screen.point.x,
                pixel_y=result.screen.point.y,
                clamped=result.screen.clamped,
            )
        elif result.status is CursorPipelineStatus.FEATURE_UNAVAILABLE:
            self._publish(
                CursorDiagnosticsStatus.STALE,
                "Gaze feature is unavailable.",
                gate_state=result.gate.state,
            )
        else:
            self._publish(
                CursorDiagnosticsStatus.BLOCKED,
                f"Cursor candidate blocked: {result.gate.state.value.replace('_', ' ')}.",
                gate_state=result.gate.state,
            )

    def _publish_result_state(self, message: str) -> CursorDiagnosticsSnapshot:
        assert self._pipeline is not None
        return self._publish(
            CursorDiagnosticsStatus.BLOCKED,
            message,
            gate_state=self._pipeline.gate_snapshot.state,
        )

    def _publish(
        self,
        status: CursorDiagnosticsStatus,
        message: str,
        *,
        gate_state: CursorGateState | None = None,
        normalized_x: float | None = None,
        normalized_y: float | None = None,
        pixel_x: int | None = None,
        pixel_y: int | None = None,
        clamped: bool = False,
    ) -> CursorDiagnosticsSnapshot:
        self._snapshot = CursorDiagnosticsSnapshot(
            status,
            message,
            gate_state,
            normalized_x,
            normalized_y,
            pixel_x,
            pixel_y,
            clamped,
        )
        self.snapshot_changed.emit(self._snapshot)
        return self._snapshot

    def _now(self) -> float:
        value = self._clock()
        if not _non_negative_finite(value):
            raise RuntimeError("Cursor diagnostics clock must be finite and non-negative")
        return float(value)


def cursor_diagnostics_snapshot(value: object) -> CursorDiagnosticsSnapshot:
    if not isinstance(value, CursorDiagnosticsSnapshot):
        raise TypeError("Expected CursorDiagnosticsSnapshot")
    return value


def _positive_finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _non_negative_finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )
