"""Live smooth-pursuit gaze calibration collection."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from meyes.domain.observations import GazeFeatureObservation, GazeFeatureVector


class CalibrationTargetName(StrEnum):
    """Stable screen-region identifiers retained for fit coverage evidence."""

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
    """One normalized screen region used for coverage and compatibility."""

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

_PURSUIT_ANCHOR_NAMES = (
    CalibrationTargetName.TOP_LEFT,
    CalibrationTargetName.TOP_CENTER,
    CalibrationTargetName.TOP_RIGHT,
    CalibrationTargetName.MIDDLE_RIGHT,
    CalibrationTargetName.CENTER,
    CalibrationTargetName.MIDDLE_LEFT,
    CalibrationTargetName.BOTTOM_LEFT,
    CalibrationTargetName.BOTTOM_CENTER,
    CalibrationTargetName.BOTTOM_RIGHT,
)


class CalibrationSessionState(StrEnum):
    """Lifecycle of one volatile smooth-pursuit calibration session."""

    IDLE = "idle"
    AWAITING_TARGET = "awaiting_target"
    COLLECTING = "collecting"
    TARGET_COMPLETE = "target_complete"
    TARGET_FAILED = "target_failed"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class CalibrationCaptureStatus(StrEnum):
    """Result of offering one gaze feature to the live collector."""

    ACCEPTED = "accepted"
    TARGET_COMPLETE = "target_complete"
    NOT_COLLECTING = "not_collecting"
    FEATURE_UNAVAILABLE = "feature_unavailable"
    INVALID_METADATA = "invalid_metadata"
    BEFORE_TRAJECTORY = "before_trajectory"
    AFTER_TRAJECTORY = "after_trajectory"
    OUT_OF_ORDER = "out_of_order"
    OUT_OF_RANGE = "out_of_range"
    EYE_DISAGREEMENT = "eye_disagreement"
    INCONSISTENT_COMBINED = "inconsistent_combined"
    STATISTICAL_OUTLIER = "statistical_outlier"
    ATTEMPT_LIMIT = "attempt_limit"


class PursuitAttentionState(StrEnum):
    """Live evidence that the eye features follow the displayed target."""

    WAITING = "waiting"
    ACQUIRING = "acquiring"
    FOLLOWING = "following"
    NOT_FOLLOWING = "not_following"


@dataclass(frozen=True, slots=True)
class PursuitTargetPosition:
    """One timestamped normalized position along the target trajectory."""

    x: float
    y: float
    elapsed_seconds: float
    progress: float
    segment_index: int
    segment_count: int
    region: CalibrationTargetName


class SmoothPursuitTrajectory:
    """Bounded serpentine path with cosine-eased movement between nine regions."""

    def __init__(
        self,
        *,
        initial_hold_seconds: float = 0.75,
        leg_duration_seconds: float = 1.75,
        final_hold_seconds: float = 0.5,
    ) -> None:
        for value, label in (
            (initial_hold_seconds, "Initial hold"),
            (leg_duration_seconds, "Leg duration"),
            (final_hold_seconds, "Final hold"),
        ):
            if not _finite_number(value) or value < 0:
                raise ValueError(f"{label} must be finite and non-negative")
        if leg_duration_seconds < 0.25:
            raise ValueError("Leg duration must be at least 0.25 seconds")
        self._initial_hold_seconds = float(initial_hold_seconds)
        self._leg_duration_seconds = float(leg_duration_seconds)
        self._final_hold_seconds = float(final_hold_seconds)
        targets = {target.name: target for target in CALIBRATION_TARGETS}
        self._anchors = tuple(targets[name] for name in _PURSUIT_ANCHOR_NAMES)

    @property
    def duration_seconds(self) -> float:
        return (
            self._initial_hold_seconds
            + (len(self._anchors) - 1) * self._leg_duration_seconds
            + self._final_hold_seconds
        )

    @property
    def segment_count(self) -> int:
        return len(self._anchors) - 1

    def position_at(self, elapsed_seconds: float) -> PursuitTargetPosition:
        """Return a clamped, deterministic target position for elapsed monotonic time."""

        if not _finite_number(elapsed_seconds):
            raise ValueError("Trajectory elapsed time must be finite")
        elapsed = min(max(float(elapsed_seconds), 0.0), self.duration_seconds)
        movement_elapsed = elapsed - self._initial_hold_seconds
        if movement_elapsed <= 0:
            x = self._anchors[0].x
            y = self._anchors[0].y
            segment_index = 0
        else:
            movement_duration = self.segment_count * self._leg_duration_seconds
            bounded_movement = min(movement_elapsed, movement_duration)
            raw_segment = bounded_movement / self._leg_duration_seconds
            segment_index = min(int(raw_segment), self.segment_count - 1)
            local = min(max(raw_segment - segment_index, 0.0), 1.0)
            eased = (1.0 - math.cos(math.pi * local)) / 2.0
            start = self._anchors[segment_index]
            end = self._anchors[segment_index + 1]
            x = start.x + (end.x - start.x) * eased
            y = start.y + (end.y - start.y) * eased
        region = _nearest_region(x, y).name
        return PursuitTargetPosition(
            x=x,
            y=y,
            elapsed_seconds=elapsed,
            progress=elapsed / self.duration_seconds,
            segment_index=segment_index,
            segment_count=self.segment_count,
            region=region,
        )


@dataclass(frozen=True, slots=True)
class CalibrationSample:
    """One live eye feature paired with the exact displayed target position."""

    target: CalibrationTargetName
    source_sequence: int
    capture_timestamp: float
    feature: GazeFeatureVector
    screen_x: float | None = None
    screen_y: float | None = None

    def __post_init__(self) -> None:
        if (self.screen_x is None) != (self.screen_y is None):
            raise ValueError("Continuous calibration coordinates must be provided together")

    @property
    def target_position(self) -> tuple[float, float]:
        """Resolve continuous coordinates or the legacy region anchor."""

        if self.screen_x is not None and self.screen_y is not None:
            return self.screen_x, self.screen_y
        anchor = _target(self.target)
        return anchor.x, anchor.y


@dataclass(frozen=True, slots=True)
class CalibrationSnapshot:
    """Immutable live progress and pursuit-attention evidence."""

    state: CalibrationSessionState
    target_index: int
    target: CalibrationTarget | None
    accepted_for_target: int
    attempts_for_target: int
    samples_per_target: int
    max_attempts_per_target: int
    completed_targets: int
    total_samples: int
    progress: float = 0.0
    duration_seconds: float = 0.0
    rejected_samples: int = 0
    attention_state: PursuitAttentionState = PursuitAttentionState.WAITING
    horizontal_correlation: float | None = None
    vertical_correlation: float | None = None
    target_position: PursuitTargetPosition | None = None
    failure_reason: str | None = None
    covered_targets: tuple[CalibrationTargetName, ...] = ()


@dataclass(frozen=True, slots=True)
class CalibrationCaptureResult:
    """One live sample decision and the resulting session snapshot."""

    status: CalibrationCaptureStatus
    snapshot: CalibrationSnapshot
    sample: CalibrationSample | None = None


class CalibrationSession:
    """Collect and validate an automatically synchronized smooth-pursuit sweep."""

    def __init__(
        self,
        *,
        samples_per_target: int = 6,
        max_attempts_per_target: int = 600,
        minimum_feature: float = -0.5,
        maximum_feature: float = 1.5,
        maximum_eye_disagreement: float = 0.4,
        minimum_axis_correlation: float = 0.2,
        trajectory: SmoothPursuitTrajectory | None = None,
        finish_grace_seconds: float = 0.75,
    ) -> None:
        if (
            isinstance(samples_per_target, bool)
            or not isinstance(samples_per_target, int)
            or not 3 <= samples_per_target <= 120
        ):
            raise ValueError("Samples per region must be an integer within 3..120")
        if (
            isinstance(max_attempts_per_target, bool)
            or not isinstance(max_attempts_per_target, int)
            or not samples_per_target <= max_attempts_per_target <= 600
        ):
            raise ValueError("Maximum attempts per region must cover the sample quota and be <=600")
        if not _finite_number(minimum_feature) or not _finite_number(maximum_feature):
            raise ValueError("Feature bounds must be finite")
        if minimum_feature >= maximum_feature:
            raise ValueError("Minimum feature must be lower than maximum feature")
        if not _finite_number(maximum_eye_disagreement) or maximum_eye_disagreement < 0:
            raise ValueError("Maximum eye disagreement must be finite and non-negative")
        if not _finite_number(minimum_axis_correlation) or not 0 <= minimum_axis_correlation <= 1:
            raise ValueError("Minimum axis correlation must be within 0..1")
        if not _finite_number(finish_grace_seconds) or not 0 <= finish_grace_seconds <= 5:
            raise ValueError("Finish grace must be within 0..5 seconds")
        if trajectory is not None and not isinstance(trajectory, SmoothPursuitTrajectory):
            raise TypeError("Expected SmoothPursuitTrajectory or None")
        self._samples_per_target = samples_per_target
        self._max_attempts_per_target = max_attempts_per_target
        self._minimum_feature = float(minimum_feature)
        self._maximum_feature = float(maximum_feature)
        self._maximum_eye_disagreement = float(maximum_eye_disagreement)
        self._minimum_axis_correlation = float(minimum_axis_correlation)
        self._trajectory = trajectory or SmoothPursuitTrajectory()
        self._finish_grace_seconds = float(finish_grace_seconds)
        self._state = CalibrationSessionState.IDLE
        self._samples: list[CalibrationSample] = []
        self._region_attempts: Counter[CalibrationTargetName] = Counter()
        self._rejected_samples = 0
        self._last_source_sequence = 0
        self._last_capture_timestamp: float | None = None
        self._start_timestamp: float | None = None
        self._last_position: PursuitTargetPosition | None = None
        self._failure_reason: str | None = None

    @property
    def trajectory(self) -> SmoothPursuitTrajectory:
        return self._trajectory

    @property
    def snapshot(self) -> CalibrationSnapshot:
        """Return current progress without exposing mutable storage."""

        counts = Counter(sample.target for sample in self._samples)
        position = self._last_position
        target = _target(position.region) if position is not None else None
        if self._state is CalibrationSessionState.AWAITING_TARGET:
            target = CALIBRATION_TARGETS[0]
            position = self._trajectory.position_at(0.0)
        if self._state in {
            CalibrationSessionState.IDLE,
            CalibrationSessionState.CANCELLED,
            CalibrationSessionState.COMPLETE,
        }:
            target = None
        target_index = 0 if target is None else _target_index(target.name)
        horizontal, vertical = self._correlations()
        return CalibrationSnapshot(
            state=self._state,
            target_index=target_index,
            target=target,
            accepted_for_target=0 if target is None else counts[target.name],
            attempts_for_target=0 if target is None else self._region_attempts[target.name],
            samples_per_target=self._samples_per_target,
            max_attempts_per_target=self._max_attempts_per_target,
            completed_targets=sum(
                counts[target_item.name] >= self._samples_per_target
                for target_item in CALIBRATION_TARGETS
            ),
            total_samples=len(self._samples),
            progress=(
                1.0
                if self._state is CalibrationSessionState.COMPLETE
                else (0.0 if position is None else position.progress)
            ),
            duration_seconds=self._trajectory.duration_seconds,
            rejected_samples=self._rejected_samples,
            attention_state=self._attention_state(horizontal, vertical),
            horizontal_correlation=horizontal,
            vertical_correlation=vertical,
            target_position=position,
            failure_reason=self._failure_reason,
            covered_targets=tuple(
                target_item.name
                for target_item in CALIBRATION_TARGETS
                if counts[target_item.name] >= self._samples_per_target
            ),
        )

    @property
    def samples(self) -> tuple[CalibrationSample, ...]:
        return tuple(self._samples)

    def start(self) -> CalibrationSnapshot:
        """Prepare a fresh sweep; the presentation starts it after a countdown."""

        self._clear()
        self._state = CalibrationSessionState.AWAITING_TARGET
        self._last_position = self._trajectory.position_at(0.0)
        return self.snapshot

    def begin_target(self, start_timestamp: float = 0.0) -> CalibrationSnapshot:
        """Begin or retry the single continuous pursuit trajectory."""

        if self._state not in {
            CalibrationSessionState.AWAITING_TARGET,
            CalibrationSessionState.TARGET_FAILED,
        }:
            raise RuntimeError("The smooth-pursuit sweep cannot start")
        if not _finite_number(start_timestamp) or start_timestamp < 0:
            raise ValueError("Pursuit start timestamp must be finite and non-negative")
        if self._state is CalibrationSessionState.TARGET_FAILED:
            self._clear_collection()
        self._start_timestamp = float(start_timestamp)
        self._last_position = self._trajectory.position_at(0.0)
        self._failure_reason = None
        self._state = CalibrationSessionState.COLLECTING
        return self.snapshot

    def position_at(self, timestamp: float) -> PursuitTargetPosition:
        """Resolve the displayed target from the same monotonic clock as camera captures."""

        if self._start_timestamp is None:
            return self._trajectory.position_at(0.0)
        if not _finite_number(timestamp):
            raise ValueError("Pursuit timestamp must be finite")
        return self._trajectory.position_at(float(timestamp) - self._start_timestamp)

    def add_feature(self, feature: GazeFeatureObservation) -> CalibrationCaptureResult:
        """Pair one camera feature with the target shown at its capture timestamp."""

        if not isinstance(feature, GazeFeatureObservation):
            raise TypeError("Expected GazeFeatureObservation")
        if self._state is not CalibrationSessionState.COLLECTING:
            return self._result(CalibrationCaptureStatus.NOT_COLLECTING)
        status, vector = self._validate_feature(feature)
        if status is not CalibrationCaptureStatus.ACCEPTED or vector is None:
            self._rejected_samples += 1
            return self._result(status)
        assert self._start_timestamp is not None
        elapsed = feature.capture_timestamp - self._start_timestamp
        if elapsed < 0:
            self._rejected_samples += 1
            return self._result(CalibrationCaptureStatus.BEFORE_TRAJECTORY)
        if elapsed > self._trajectory.duration_seconds + self._finish_grace_seconds:
            self._rejected_samples += 1
            return self._result(CalibrationCaptureStatus.AFTER_TRAJECTORY)
        position = self._trajectory.position_at(elapsed)
        self._last_position = position
        self._region_attempts[position.region] += 1
        sample = CalibrationSample(
            target=position.region,
            source_sequence=feature.source_sequence,
            capture_timestamp=feature.capture_timestamp,
            feature=vector,
            screen_x=position.x,
            screen_y=position.y,
        )
        self._samples.append(sample)
        if self._region_attempts[position.region] > self._max_attempts_per_target:
            self._state = CalibrationSessionState.TARGET_FAILED
            region_label = _target(position.region).label.lower()
            self._failure_reason = (
                f"Too many camera frames accumulated in {region_label}. "
                "Check camera responsiveness and retry."
            )
            return self._result(CalibrationCaptureStatus.ATTEMPT_LIMIT, sample)
        return self._result(CalibrationCaptureStatus.ACCEPTED, sample)

    def finish(self, finish_timestamp: float) -> CalibrationSnapshot:
        """Validate spatial coverage and target-following evidence after the sweep."""

        if self._state is not CalibrationSessionState.COLLECTING:
            raise RuntimeError("Only an active smooth-pursuit sweep can finish")
        if not _finite_number(finish_timestamp):
            raise ValueError("Pursuit finish timestamp must be finite")
        assert self._start_timestamp is not None
        elapsed = float(finish_timestamp) - self._start_timestamp
        if elapsed < self._trajectory.duration_seconds:
            raise RuntimeError("The smooth-pursuit trajectory is not complete")
        self._last_position = self._trajectory.position_at(self._trajectory.duration_seconds)
        counts = Counter(sample.target for sample in self._samples)
        missing = [
            target.label
            for target in CALIBRATION_TARGETS
            if counts[target.name] < self._samples_per_target
        ]
        horizontal, vertical = self._correlations()
        reasons: list[str] = []
        if missing:
            reasons.append(f"insufficient live samples in {', '.join(missing)}")
        if horizontal is None or abs(horizontal) < self._minimum_axis_correlation:
            reasons.append("horizontal eye movement did not follow the target reliably")
        if vertical is None or abs(vertical) < self._minimum_axis_correlation:
            reasons.append("vertical eye movement did not follow the target reliably")
        if reasons:
            self._state = CalibrationSessionState.TARGET_FAILED
            self._failure_reason = "; ".join(reasons).capitalize() + "."
        else:
            self._state = CalibrationSessionState.COMPLETE
            self._failure_reason = None
        return self.snapshot

    def advance(self) -> CalibrationSnapshot:
        """Reject obsolete manual point progression explicitly."""

        raise RuntimeError("Smooth-pursuit calibration advances automatically")

    def cancel(self) -> CalibrationSnapshot:
        self._clear()
        self._state = CalibrationSessionState.CANCELLED
        return self.snapshot

    def reset(self) -> CalibrationSnapshot:
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

    def _correlations(self) -> tuple[float | None, float | None]:
        if len(self._samples) < 12:
            return None, None
        horizontal = _pearson(
            tuple(sample.target_position[0] for sample in self._samples),
            tuple(sample.feature.horizontal for sample in self._samples),
        )
        vertical = _pearson(
            tuple(sample.target_position[1] for sample in self._samples),
            tuple(sample.feature.vertical for sample in self._samples),
        )
        return horizontal, vertical

    def _attention_state(
        self,
        horizontal: float | None,
        vertical: float | None,
    ) -> PursuitAttentionState:
        if self._state in {
            CalibrationSessionState.IDLE,
            CalibrationSessionState.AWAITING_TARGET,
            CalibrationSessionState.CANCELLED,
        }:
            return PursuitAttentionState.WAITING
        if horizontal is None or vertical is None:
            return PursuitAttentionState.ACQUIRING
        if (
            abs(horizontal) >= self._minimum_axis_correlation
            and abs(vertical) >= self._minimum_axis_correlation
        ):
            return PursuitAttentionState.FOLLOWING
        return PursuitAttentionState.NOT_FOLLOWING

    def _result(
        self,
        status: CalibrationCaptureStatus,
        sample: CalibrationSample | None = None,
    ) -> CalibrationCaptureResult:
        return CalibrationCaptureResult(status=status, snapshot=self.snapshot, sample=sample)

    def _clear_collection(self) -> None:
        self._samples.clear()
        self._region_attempts.clear()
        self._rejected_samples = 0
        self._last_source_sequence = 0
        self._last_capture_timestamp = None
        self._start_timestamp = None
        self._last_position = None
        self._failure_reason = None

    def _clear(self) -> None:
        self._state = CalibrationSessionState.IDLE
        self._clear_collection()


def _nearest_region(x: float, y: float) -> CalibrationTarget:
    return min(CALIBRATION_TARGETS, key=lambda target: math.hypot(x - target.x, y - target.y))


def _target(name: CalibrationTargetName) -> CalibrationTarget:
    return next(target for target in CALIBRATION_TARGETS if target.name is name)


def _target_index(name: CalibrationTargetName) -> int:
    return next(index for index, target in enumerate(CALIBRATION_TARGETS) if target.name is name)


def _pearson(first: tuple[float, ...], second: tuple[float, ...]) -> float | None:
    if len(first) != len(second) or len(first) < 2:
        return None
    first_mean = sum(first) / len(first)
    second_mean = sum(second) / len(second)
    first_delta = tuple(value - first_mean for value in first)
    second_delta = tuple(value - second_mean for value in second)
    numerator = sum(left * right for left, right in zip(first_delta, second_delta, strict=True))
    first_energy = sum(value * value for value in first_delta)
    second_energy = sum(value * value for value in second_delta)
    denominator = math.sqrt(first_energy * second_energy)
    if denominator <= 1e-12:
        return None
    result = numerator / denominator
    return max(-1.0, min(1.0, result))


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
