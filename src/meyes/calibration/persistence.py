"""Versioned, checksummed, fail-closed accepted-calibration persistence."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import stat
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from meyes.calibration.acceptance import (
    AcceptedCalibration,
    CalibrationAcceptancePolicy,
    CalibrationAcceptanceState,
    evaluate_calibration_acceptance,
)
from meyes.calibration.mapper import (
    CalibrationFitResult,
    CalibrationValidation,
    PolynomialCalibrationMapper,
)
from meyes.util.paths import AppPaths

CALIBRATION_ENVELOPE_SCHEMA_VERSION = 1
MAXIMUM_CALIBRATION_FILE_BYTES = 64 * 1024
_DIGEST_HEX_LENGTH = 64
_WINDOWS_REPARSE_POINT = 0x0400

Clock = Callable[[], datetime]


class DuplicateCalibrationKeyError(ValueError):
    """Reject ambiguous JSON objects before schema validation."""


@dataclass(frozen=True, slots=True)
class CalibrationLoadResult:
    """Recovered proof token or a bounded fail-closed explanation."""

    calibration: AcceptedCalibration | None
    warning: str | None = None
    recovered_from: Path | None = None


class AcceptedCalibrationRepository:
    """Persist mapper evidence without activating any runtime consumer."""

    def __init__(self, paths: AppPaths, clock: Clock | None = None) -> None:
        if not isinstance(paths, AppPaths):
            raise TypeError("Expected AppPaths")
        self._paths = paths
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def path(self) -> Path:
        return self._paths.calibration_file

    def save(
        self,
        calibration: AcceptedCalibration,
        policy: CalibrationAcceptancePolicy,
    ) -> Path:
        """Atomically persist only evidence accepted by the supplied policy."""
        if not isinstance(calibration, AcceptedCalibration):
            raise TypeError("Expected AcceptedCalibration")
        if not isinstance(policy, CalibrationAcceptancePolicy):
            raise TypeError("Expected CalibrationAcceptancePolicy")
        decision = evaluate_calibration_acceptance(policy, calibration.fit_result.validation)
        if decision.state is not CalibrationAcceptanceState.ACCEPTED:
            raise ValueError("Calibration evidence does not satisfy the persistence policy")
        payload = _payload(calibration.fit_result, policy)
        envelope = {
            "schema_version": CALIBRATION_ENVELOPE_SCHEMA_VERSION,
            "payload": payload,
            "payload_sha256": _payload_digest(payload),
        }
        serialized = json.dumps(
            envelope,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        self._paths.ensure_directories()
        self._assert_safe_path()
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".accepted-calibration-",
            suffix=".tmp",
            dir=self._paths.data_dir,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                descriptor = -1
                stream.write(f"{serialized}\n")
                stream.flush()
                os.fsync(stream.fileno())
            self._assert_safe_path()
            os.replace(temporary, self.path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)
        return self.path

    def load(
        self,
        policy: CalibrationAcceptancePolicy | None,
    ) -> CalibrationLoadResult:
        """Recover proof only under the exact policy that originally accepted it."""
        if policy is not None and not isinstance(policy, CalibrationAcceptancePolicy):
            raise TypeError("Expected CalibrationAcceptancePolicy or None")
        if policy is None:
            return CalibrationLoadResult(
                None,
                "Accepted calibration recovery is disabled because no policy is configured.",
            )
        if not self.path.exists():
            return CalibrationLoadResult(None)
        try:
            self._assert_safe_path()
            if self.path.stat().st_size > MAXIMUM_CALIBRATION_FILE_BYTES:
                raise ValueError("Calibration file exceeds the 64 KiB limit")
            raw = self.path.read_text(encoding="utf-8")
            document = json.loads(
                raw,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_json_constant,
            )
            fit_result, stored_policy = _decode_envelope(document)
            if stored_policy != policy:
                return CalibrationLoadResult(
                    None,
                    "Stored calibration policy does not match the current policy; recalibrate.",
                )
            acceptance = evaluate_calibration_acceptance(policy, fit_result.validation)
            if acceptance.state is not CalibrationAcceptanceState.ACCEPTED:
                raise ValueError("Stored calibration evidence no longer satisfies its policy")
            return CalibrationLoadResult(AcceptedCalibration(fit_result, acceptance))
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            DuplicateCalibrationKeyError,
            TypeError,
            ValueError,
        ) as error:
            backup = self._backup_invalid_file()
            return CalibrationLoadResult(
                None,
                f"Stored calibration was invalid and remains inactive: {error}",
                backup,
            )

    def _assert_safe_path(self) -> None:
        data_directory = self._paths.data_dir
        directory_metadata = data_directory.lstat()
        directory_attributes = int(getattr(directory_metadata, "st_file_attributes", 0))
        if (
            stat.S_ISLNK(directory_metadata.st_mode)
            or directory_attributes & _WINDOWS_REPARSE_POINT
        ):
            raise OSError("Calibration directory must not be a link or reparse point")
        if self.path.parent.resolve(strict=True) != data_directory.resolve(strict=True):
            raise OSError("Calibration path escapes the configured data directory")
        if not self.path.exists():
            return
        metadata = self.path.lstat()
        attributes = int(getattr(metadata, "st_file_attributes", 0))
        if stat.S_ISLNK(metadata.st_mode) or attributes & _WINDOWS_REPARSE_POINT:
            raise OSError("Calibration path must not be a link or reparse point")
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("Calibration path must be a regular file")

    def _backup_invalid_file(self) -> Path | None:
        if not self.path.exists():
            return None
        try:
            self._assert_safe_path()
            stamp = self._clock().astimezone(UTC).strftime("%Y%m%d-%H%M%S-%f")
            backup = self.path.with_name(f"accepted-calibration.invalid-{stamp}.json")
            try:
                backup.lstat()
            except FileNotFoundError:
                pass
            else:
                return None
            self.path.replace(backup)
        except OSError:
            return None
        return backup


def _payload(
    fit_result: CalibrationFitResult,
    policy: CalibrationAcceptancePolicy,
) -> dict[str, object]:
    mapper = fit_result.mapper
    if not isinstance(mapper, PolynomialCalibrationMapper):
        raise TypeError("Only polynomial calibration mappers can be persisted")
    validation = fit_result.validation
    evaluate_calibration_acceptance(policy, validation)
    return {
        "mapper": {
            "horizontal_coefficients": list(mapper.horizontal_coefficients),
            "vertical_coefficients": list(mapper.vertical_coefficients),
        },
        "policy": {
            "maximum_root_mean_square_error": policy.maximum_root_mean_square_error,
            "maximum_mean_error": policy.maximum_mean_error,
            "maximum_error": policy.maximum_error,
            "minimum_holdout_samples": policy.minimum_holdout_samples,
        },
        "validation": {
            "sample_count": validation.sample_count,
            "root_mean_square_error": validation.root_mean_square_error,
            "mean_error": validation.mean_error,
            "maximum_error": validation.maximum_error,
        },
    }


def _decode_envelope(document: object) -> tuple[CalibrationFitResult, CalibrationAcceptancePolicy]:
    envelope = _mapping(document, "Calibration envelope")
    _exact_keys(envelope, {"schema_version", "payload", "payload_sha256"}, "envelope")
    if _integer(envelope["schema_version"], "schema_version") != 1:
        raise ValueError("Unsupported calibration schema version")
    payload = _mapping(envelope["payload"], "Calibration payload")
    digest = envelope["payload_sha256"]
    if (
        not isinstance(digest, str)
        or len(digest) != _DIGEST_HEX_LENGTH
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("Calibration payload digest is malformed")
    if not hmac.compare_digest(digest, _payload_digest(payload)):
        raise ValueError("Calibration payload checksum does not match")
    _exact_keys(payload, {"mapper", "policy", "validation"}, "payload")

    mapper_payload = _mapping(payload["mapper"], "Calibration mapper")
    _exact_keys(
        mapper_payload,
        {"horizontal_coefficients", "vertical_coefficients"},
        "mapper",
    )
    mapper = PolynomialCalibrationMapper(
        _coefficients(mapper_payload["horizontal_coefficients"], "horizontal"),
        _coefficients(mapper_payload["vertical_coefficients"], "vertical"),
    )

    validation_payload = _mapping(payload["validation"], "Calibration validation")
    _exact_keys(
        validation_payload,
        {"sample_count", "root_mean_square_error", "mean_error", "maximum_error"},
        "validation",
    )
    validation = CalibrationValidation(
        _integer(validation_payload["sample_count"], "sample_count"),
        _number(validation_payload["root_mean_square_error"], "root_mean_square_error"),
        _number(validation_payload["mean_error"], "mean_error"),
        _number(validation_payload["maximum_error"], "maximum_error"),
    )

    policy_payload = _mapping(payload["policy"], "Calibration policy")
    _exact_keys(
        policy_payload,
        {
            "maximum_root_mean_square_error",
            "maximum_mean_error",
            "maximum_error",
            "minimum_holdout_samples",
        },
        "policy",
    )
    policy = CalibrationAcceptancePolicy(
        _number(
            policy_payload["maximum_root_mean_square_error"],
            "maximum_root_mean_square_error",
        ),
        _number(policy_payload["maximum_mean_error"], "maximum_mean_error"),
        _number(policy_payload["maximum_error"], "maximum_error"),
        _integer(policy_payload["minimum_holdout_samples"], "minimum_holdout_samples"),
    )
    return CalibrationFitResult(mapper, validation), policy


def _payload_digest(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError(f"{label} must be an object")
    return value


def _exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ValueError(f"Calibration {label} keys do not match schema")


def _coefficients(value: object, axis: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != 6:
        raise ValueError(f"Calibration {axis} coefficients must contain six values")
    return tuple(_number(item, f"{axis} coefficient") for item in value)


def _number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"Calibration {label} must be finite")
    return float(value)


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Calibration {label} must be an integer")
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateCalibrationKeyError(f"Duplicate calibration JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"Non-finite JSON constant is not allowed: {value}")
