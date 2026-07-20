"""Bounded nine-point calibration sample collection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from meyes.domain.observations import GazeFeatureObservation, GazeFeatureVector


class CalibrationTargetName(StrEnum):
    """Stable identifiers for the guided nine-point order."""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


@dataclass(frozen=True, slots=True)
class CalibrationTarget:
    """One normalized screen target used only as a calibration label."""

    name: CalibrationTargetName
    label: str
    x: float
    y: float


CALIBRATION_TARGETS = (
    CalibrationTarget(CalibrationTargetName.TOP_LEFT, "Top left", 0.1, 0.1),
    CalibrationTarget(CalibrationTargetName.TOP_CENTER, "Top center", 0.5, 0.1),
    CalibrationTarget(CalibrationTargetName.TOP_RIGHT, "Top right", 0.9, 0.1),
    CalibrationTarget(CalibrationTargetName.MIDDLE_LEFT, "Middle left", 0.1, 0.5),
    CalibrationTarget(CalibrationTargetName.CENTER, "Center", 0.5, 0.5),
    CalibrationTarget(CalibrationTargetName.MIDDLE_RIGHT, "Middle right", 0.9, 0.5),
    CalibrationTarget(CalibrationTargetName.BOTTOM_LEFT, "Bottom left", 0.1, 0.9),
    CalibrationTarget(CalibrationTargetName.BOTTOM_CENTER, "Bottom center", 0.5, 0.9),
    CalibrationTarget(CalibrationTargetName.BOTTOM_RIGHT, "Bottom right", 0.9, 0.9),
)


class CalibrationSessionState(StrEnum):
    """Lifecycle of one volatile calibration collection session."""

    IDLE = "idle"
    AWAITING_TARGET = "awaiting_target"
    COLLECTING = "collecting"
    TARGET_COMPLETE = "target_complete"
    TARGET_FAILED = "target_failed"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class CalibrationCaptureStatus(StrEnum):
    """Result of offering one gaze feature to the collector."""

    ACCEPTED = "accepted"
    TARGET_COMPLETE = "target_complete"
    NOT_COLLECTING = "not_collecting"
    FEATURE_UNAVAILABLE = "feature_unavailable"
    INVALID_METADATA = "invalid_metadata"
    OUT_OF_ORDER = "out_of_order"
    OUT_OF_RANGE = "out_of_range"
    EYE_DISAGREEMENT = "eye_disagreement"
    INCONSISTENT_COMBINED = "inconsistent_combined"
    ATTEMPT_LIMIT = "attempt_limit"


@dataclass(frozen=True, slots=True)
class CalibrationSample:
    """One accepted volatile feature paired with the current target."""

    target: CalibrationTargetName
    source_sequence: int
    capture_timestamp: float
    feature: GazeFeatureVector


@dataclass(frozen=True, slots=True)
class CalibrationSnapshot:
    """Immutable progress state for a future Qt calibration page."""

    state: CalibrationSessionState
    target_index: int
    target: CalibrationTarget | None
    accepted_for_target: int
    attempts_for_target: int
    samples_per_target: int
    max_attempts_per_target: int
    completed_targets: int
    total_samples: int


@dataclass(frozen=True, slots=True)
class CalibrationCaptureResult:
    """One sample decision and the resulting session snapshot."""

    status: CalibrationCaptureStatus
    snapshot: CalibrationSnapshot
    sample: CalibrationSample | None = None


class CalibrationSession:
    """Collect a bounded number of ordered, quality-gated samples at nine targets."""

    def __init__(
        self,
        *,
        samples_per_target: int = 12,
        max_attempts_per_target: int = 36,
        minimum_feature: float = -0.5,
        maximum_feature: float = 1.5,
        maximum_eye_disagreement: float = 0.4,
    ) -> None:
        if (
            isinstance(samples_per_target, bool)
            or not isinstance(samples_per_target, int)
            or not 3 <= samples_per_target <= 120
        ):
            raise ValueError("Samples per target must be an integer within 3..120")
        if (
            isinstance(max_attempts_per_target, bool)
            or not isinstance(max_attempts_per_target, int)
            or not samples_per_target <= max_attempts_per_target <= 600
        ):
            raise ValueError("Maximum attempts must be within the sample quota and 600")
        if not _finite_number(minimum_feature) or not _finite_number(maximum_feature):
            raise ValueError("Feature bounds must be finite")
        if minimum_feature >= maximum_feature:
            raise ValueError("Minimum feature must be lower than maximum feature")
        if not _finite_number(maximum_eye_disagreement) or maximum_eye_disagreement < 0:
            raise ValueError("Maximum eye disagreement must be finite and non-negative")
        self._samples_per_target = samples_per_target
        self._max_attempts_per_target = max_attempts_per_target
        self._minimum_feature = float(minimum_feature)
        self._maximum_feature = float(maximum_feature)
        self._maximum_eye_disagreement = float(maximum_eye_disagreement)
        self._state = CalibrationSessionState.IDLE
        self._target_index = 0
        self._attempts_for_target = 0
        self._samples: list[CalibrationSample] = []
        self._last_source_sequence = 0
        self._last_capture_timestamp: float | None = None

    @property
    def snapshot(self) -> CalibrationSnapshot:
        """Return current progress without exposing mutable storage."""
        target = (
            CALIBRATION_TARGETS[self._target_index]
            if self._state
            not in {
                CalibrationSessionState.IDLE,
                CalibrationSessionState.CANCELLED,
                CalibrationSessionState.COMPLETE,
            }
            else None
        )
        accepted = sum(
            sample.target == CALIBRATION_TARGETS[self._target_index].name
            for sample in self._samples
        )
        completed = self._target_index
        if self._state is CalibrationSessionState.COMPLETE:
            completed = len(CALIBRATION_TARGETS)
        return CalibrationSnapshot(
            state=self._state,
            target_index=self._target_index,
            target=target,
            accepted_for_target=accepted if target is not None else 0,
            attempts_for_target=self._attempts_for_target if target is not None else 0,
            samples_per_target=self._samples_per_target,
            max_attempts_per_target=self._max_attempts_per_target,
            completed_targets=completed,
            total_samples=len(self._samples),
        )

    @property
    def samples(self) -> tuple[CalibrationSample, ...]:
        """Return the accepted samples as an immutable snapshot."""
        return tuple(self._samples)

    def start(self) -> CalibrationSnapshot:
        """Start a fresh volatile session at the top-left target."""
        self._clear()
        self._state = CalibrationSessionState.AWAITING_TARGET
        return self.snapshot

    def begin_target(self) -> CalibrationSnapshot:
        """Arm collection for the current target or retry a failed target."""
        if self._state not in {
            CalibrationSessionState.AWAITING_TARGET,
            CalibrationSessionState.TARGET_FAILED,
        }:
            raise RuntimeError("The current calibration target cannot start")
        if self._state is CalibrationSessionState.TARGET_FAILED:
            target_name = CALIBRATION_TARGETS[self._target_index].name
            self._samples = [sample for sample in self._samples if sample.target != target_name]
        self._attempts_for_target = 0
        self._state = CalibrationSessionState.COLLECTING
        return self.snapshot

    def add_feature(self, feature: GazeFeatureObservation) -> CalibrationCaptureResult:
        """Offer one serialized feature to the active target collector."""
        if not isinstance(feature, GazeFeatureObservation):
            raise TypeError("Expected GazeFeatureObservation")
        if self._state is not CalibrationSessionState.COLLECTING:
            return self._result(CalibrationCaptureStatus.NOT_COLLECTING)
        self._attempts_for_target += 1
        status, vector = self._validate_feature(feature)
        sample: CalibrationSample | None = None
        if status is CalibrationCaptureStatus.ACCEPTED and vector is not None:
            target = CALIBRATION_TARGETS[self._target_index]
            sample = CalibrationSample(
                target=target.name,
                source_sequence=feature.source_sequence,
                capture_timestamp=feature.capture_timestamp,
                feature=vector,
            )
            self._samples.append(sample)
            if self.snapshot.accepted_for_target >= self._samples_per_target:
                self._state = CalibrationSessionState.TARGET_COMPLETE
                return self._result(CalibrationCaptureStatus.TARGET_COMPLETE, sample)
        if self._attempts_for_target >= self._max_attempts_per_target:
            self._state = CalibrationSessionState.TARGET_FAILED
            return self._result(CalibrationCaptureStatus.ATTEMPT_LIMIT)
        return self._result(status, sample)

    def advance(self) -> CalibrationSnapshot:
        """Advance after a complete target, or finish after bottom-right."""
        if self._state is not CalibrationSessionState.TARGET_COMPLETE:
            raise RuntimeError("Only a complete calibration target can advance")
        self._attempts_for_target = 0
        if self._target_index == len(CALIBRATION_TARGETS) - 1:
            self._state = CalibrationSessionState.COMPLETE
            return self.snapshot
        self._target_index += 1
        self._state = CalibrationSessionState.AWAITING_TARGET
        return self.snapshot

    def cancel(self) -> CalibrationSnapshot:
        """Discard all volatile samples and mark the session cancelled."""
        self._clear()
        self._state = CalibrationSessionState.CANCELLED
        return self.snapshot

    def reset(self) -> CalibrationSnapshot:
        """Discard all samples and return to idle."""
        self._clear()
        return self.snapshot

    def _validate_feature(
        self,
        feature: GazeFeatureObservation,
    ) -> tuple[CalibrationCaptureStatus, GazeFeatureVector | None]:
        if not feature.ready:
            return CalibrationCaptureStatus.FEATURE_UNAVAILABLE, None
        left, right, combined = feature.left_eye, feature.right_eye, feature.combined
        if not all(isinstance(item, GazeFeatureVector) for item in (left, right, combined)):
            return CalibrationCaptureStatus.FEATURE_UNAVAILABLE, None
        if (
            isinstance(feature.source_sequence, bool)
            or not isinstance(feature.source_sequence, int)
            or feature.source_sequence <= 0
            or not _finite_number(feature.capture_timestamp)
        ):
            return CalibrationCaptureStatus.INVALID_METADATA, None
        if feature.source_sequence <= self._last_source_sequence or (
            self._last_capture_timestamp is not None
            and feature.capture_timestamp <= self._last_capture_timestamp
        ):
            return CalibrationCaptureStatus.OUT_OF_ORDER, None
        self._last_source_sequence = feature.source_sequence
        self._last_capture_timestamp = float(feature.capture_timestamp)
        assert left is not None and right is not None and combined is not None
        values = (
            left.horizontal,
            left.vertical,
            right.horizontal,
            right.vertical,
            combined.horizontal,
            combined.vertical,
        )
        if not all(_finite_number(value) for value in values):
            return CalibrationCaptureStatus.OUT_OF_RANGE, None
        if not all(self._minimum_feature <= value <= self._maximum_feature for value in values):
            return CalibrationCaptureStatus.OUT_OF_RANGE, None
        if (
            abs(left.horizontal - right.horizontal) > self._maximum_eye_disagreement
            or abs(left.vertical - right.vertical) > self._maximum_eye_disagreement
        ):
            return CalibrationCaptureStatus.EYE_DISAGREEMENT, None
        calculated = GazeFeatureVector(
            horizontal=(left.horizontal + right.horizontal) / 2.0,
            vertical=(left.vertical + right.vertical) / 2.0,
        )
        if not (
            math.isclose(combined.horizontal, calculated.horizontal, abs_tol=1e-9)
            and math.isclose(combined.vertical, calculated.vertical, abs_tol=1e-9)
        ):
            return CalibrationCaptureStatus.INCONSISTENT_COMBINED, None
        return CalibrationCaptureStatus.ACCEPTED, calculated

    def _result(
        self,
        status: CalibrationCaptureStatus,
        sample: CalibrationSample | None = None,
    ) -> CalibrationCaptureResult:
        return CalibrationCaptureResult(status=status, snapshot=self.snapshot, sample=sample)

    def _clear(self) -> None:
        self._state = CalibrationSessionState.IDLE
        self._target_index = 0
        self._attempts_for_target = 0
        self._samples.clear()
        self._last_source_sequence = 0
        self._last_capture_timestamp = None


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
