"""Versioned, checksummed, fail-closed accepted-calibration persistence."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
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
from meyes.cursor.screen_mapping import PhysicalScreenGeometry
from meyes.util.paths import AppPaths

CALIBRATION_ENVELOPE_SCHEMA_VERSION = 2
MAXIMUM_CALIBRATION_FILE_BYTES = 64 * 1024
MAXIMUM_DELETED_CALIBRATION_BACKUPS = 20
_DIGEST_HEX_LENGTH = 64
_WINDOWS_REPARSE_POINT = 0x0400
_DELETED_BACKUP_PATTERN = re.compile(r"^accepted-calibration\.deleted-(\d{8}-\d{6}-\d{6})\.json$")

Clock = Callable[[], datetime]


class DuplicateCalibrationKeyError(ValueError):
    """Reject ambiguous JSON objects before schema validation."""


class LegacyCalibrationSchemaError(ValueError):
    """Keep a valid old envelope inactive without treating it as corrupt."""


class CalibrationPolicyMismatchError(ValueError):
    """Keep valid evidence inactive when runtime policy changed."""


@dataclass(frozen=True, slots=True)
class CalibrationProvenance:
    """Bounded context required before persisted calibration may be reused."""

    created_at_utc: datetime
    primary_screen: PhysicalScreenGeometry

    def __post_init__(self) -> None:
        if not isinstance(self.created_at_utc, datetime):
            raise TypeError("Calibration creation time must be a datetime")
        offset = self.created_at_utc.utcoffset()
        if self.created_at_utc.tzinfo is None or offset is None:
            raise ValueError("Calibration creation time must be timezone-aware")
        if offset.total_seconds() != 0:
            raise ValueError("Calibration creation time must use UTC")
        object.__setattr__(
            self,
            "created_at_utc",
            self.created_at_utc.astimezone(UTC).replace(microsecond=0),
        )
        if not isinstance(self.primary_screen, PhysicalScreenGeometry):
            raise TypeError("Expected PhysicalScreenGeometry")


@dataclass(frozen=True, slots=True)
class CalibrationLoadResult:
    """Recovered proof token or a bounded fail-closed explanation."""

    calibration: AcceptedCalibration | None
    warning: str | None = None
    recovered_from: Path | None = None
    provenance: CalibrationProvenance | None = None


@dataclass(frozen=True, slots=True)
class DeletedCalibrationBackup:
    """Read-only metadata for one recoverably forgotten envelope."""

    path: Path
    deleted_at_utc: datetime
    size_bytes: int


@dataclass(frozen=True, slots=True)
class DeletedCalibrationCatalog:
    """Bounded newest-first backup metadata plus a sanitized warning."""

    backups: tuple[DeletedCalibrationBackup, ...]
    warning: str | None = None


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
        provenance: CalibrationProvenance,
    ) -> Path:
        """Atomically persist only evidence accepted by the supplied policy."""
        if not isinstance(calibration, AcceptedCalibration):
            raise TypeError("Expected AcceptedCalibration")
        if not isinstance(policy, CalibrationAcceptancePolicy):
            raise TypeError("Expected CalibrationAcceptancePolicy")
        if not isinstance(provenance, CalibrationProvenance):
            raise TypeError("Expected CalibrationProvenance")
        decision = evaluate_calibration_acceptance(policy, calibration.fit_result.validation)
        if decision.state is not CalibrationAcceptanceState.ACCEPTED:
            raise ValueError("Calibration evidence does not satisfy the persistence policy")
        payload = _payload(calibration.fit_result, policy, provenance)
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
            calibration, provenance, _raw = _read_valid_envelope(self.path, policy)
            return CalibrationLoadResult(calibration, provenance=provenance)
        except LegacyCalibrationSchemaError as error:
            return CalibrationLoadResult(None, str(error))
        except CalibrationPolicyMismatchError as error:
            return CalibrationLoadResult(None, str(error))
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

    def forget(self) -> Path | None:
        """Move the active envelope to a recoverable timestamped backup."""
        try:
            self.path.lstat()
        except FileNotFoundError:
            return None
        self._assert_safe_path()
        stamp = self._clock().astimezone(UTC).strftime("%Y%m%d-%H%M%S-%f")
        backup = self.path.with_name(f"accepted-calibration.deleted-{stamp}.json")
        try:
            backup.lstat()
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError("Calibration deleted backup already exists")
        self.path.replace(backup)
        return backup

    def deleted_catalog(self) -> DeletedCalibrationCatalog:
        """List bounded backup metadata without reading or mutating envelope payloads."""
        if not self._paths.data_dir.exists():
            return DeletedCalibrationCatalog(())
        try:
            self._assert_safe_data_directory()
            backups: list[DeletedCalibrationBackup] = []
            ignored = 0
            for candidate in self._paths.data_dir.glob("accepted-calibration.deleted-*.json"):
                match = _DELETED_BACKUP_PATTERN.fullmatch(candidate.name)
                if match is None:
                    ignored += 1
                    continue
                try:
                    metadata = candidate.lstat()
                except OSError:
                    ignored += 1
                    continue
                attributes = int(getattr(metadata, "st_file_attributes", 0))
                if (
                    stat.S_ISLNK(metadata.st_mode)
                    or attributes & _WINDOWS_REPARSE_POINT
                    or not stat.S_ISREG(metadata.st_mode)
                ):
                    ignored += 1
                    continue
                try:
                    deleted_at = datetime.strptime(
                        match.group(1),
                        "%Y%m%d-%H%M%S-%f",
                    ).replace(tzinfo=UTC)
                except ValueError:
                    ignored += 1
                    continue
                backups.append(
                    DeletedCalibrationBackup(candidate, deleted_at, int(metadata.st_size))
                )
        except OSError:
            return DeletedCalibrationCatalog((), "Deleted calibration backups are unavailable.")
        backups.sort(key=lambda item: (item.deleted_at_utc, item.path.name), reverse=True)
        truncated = len(backups) > MAXIMUM_DELETED_CALIBRATION_BACKUPS
        visible = tuple(backups[:MAXIMUM_DELETED_CALIBRATION_BACKUPS])
        warning = None
        if ignored or truncated:
            warning = "Some deleted calibration backup metadata was ignored or omitted."
        return DeletedCalibrationCatalog(visible, warning)

    def restore(
        self,
        backup: DeletedCalibrationBackup,
        policy: CalibrationAcceptancePolicy | None,
    ) -> CalibrationLoadResult:
        """Exclusively reactivate one exact valid catalog record while retaining its backup."""
        if not isinstance(backup, DeletedCalibrationBackup):
            raise TypeError("Expected DeletedCalibrationBackup")
        if policy is not None and not isinstance(policy, CalibrationAcceptancePolicy):
            raise TypeError("Expected CalibrationAcceptancePolicy or None")
        if policy is None:
            return CalibrationLoadResult(
                None,
                "Calibration restore is disabled because no policy is configured.",
            )
        self._assert_safe_data_directory()
        try:
            self.path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError("An active accepted calibration already exists")
        catalog = self.deleted_catalog()
        if backup not in catalog.backups:
            raise ValueError("Deleted calibration backup is not an exact current catalog record")
        try:
            calibration, provenance, raw = _read_valid_envelope(backup.path, policy)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            DuplicateCalibrationKeyError,
            LegacyCalibrationSchemaError,
            CalibrationPolicyMismatchError,
            TypeError,
            ValueError,
        ) as error:
            return CalibrationLoadResult(
                None,
                f"Deleted calibration backup remains inactive: {error}",
            )
        descriptor = -1
        created = False
        try:
            descriptor = os.open(
                self.path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            created = True
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            if descriptor >= 0:
                os.close(descriptor)
            if created:
                self.path.unlink(missing_ok=True)
            raise
        return CalibrationLoadResult(calibration, provenance=provenance)

    def delete_backup(self, backup: DeletedCalibrationBackup) -> None:
        """Permanently delete one exact current catalog record without following links."""

        if not isinstance(backup, DeletedCalibrationBackup):
            raise TypeError("Expected DeletedCalibrationBackup")
        self._assert_safe_data_directory()
        if backup not in self.deleted_catalog().backups:
            raise ValueError("Deleted calibration backup is not an exact current catalog record")
        if backup.path.parent.resolve(strict=True) != self._paths.data_dir.resolve(strict=True):
            raise OSError("Deleted calibration backup escapes the configured data directory")
        metadata = backup.path.lstat()
        attributes = int(getattr(metadata, "st_file_attributes", 0))
        if (
            stat.S_ISLNK(metadata.st_mode)
            or attributes & _WINDOWS_REPARSE_POINT
            or not stat.S_ISREG(metadata.st_mode)
        ):
            raise OSError("Deleted calibration backup must be a regular non-link file")
        if int(metadata.st_size) != backup.size_bytes:
            raise OSError("Deleted calibration backup changed after cataloging")
        backup.path.unlink()

    def rollback_restored(self, backup: DeletedCalibrationBackup) -> bool:
        """Remove only an active copy that still exactly matches its retained backup."""
        if not isinstance(backup, DeletedCalibrationBackup):
            raise TypeError("Expected DeletedCalibrationBackup")
        if backup not in self.deleted_catalog().backups:
            raise ValueError("Deleted calibration backup is not an exact current catalog record")
        try:
            self.path.lstat()
        except FileNotFoundError:
            return False
        self._assert_safe_path()
        active = self.path.read_bytes()
        retained = backup.path.read_bytes()
        if active != retained:
            raise OSError("Active calibration no longer matches the restored backup")
        self.path.unlink()
        return True

    def _assert_safe_path(self) -> None:
        self._assert_safe_data_directory()
        if self.path.parent.resolve(strict=True) != self._paths.data_dir.resolve(strict=True):
            raise OSError("Calibration path escapes the configured data directory")
        if not self.path.exists():
            return
        metadata = self.path.lstat()
        attributes = int(getattr(metadata, "st_file_attributes", 0))
        if stat.S_ISLNK(metadata.st_mode) or attributes & _WINDOWS_REPARSE_POINT:
            raise OSError("Calibration path must not be a link or reparse point")
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("Calibration path must be a regular file")

    def _assert_safe_data_directory(self) -> None:
        data_directory = self._paths.data_dir
        directory_metadata = data_directory.lstat()
        directory_attributes = int(getattr(directory_metadata, "st_file_attributes", 0))
        if (
            stat.S_ISLNK(directory_metadata.st_mode)
            or directory_attributes & _WINDOWS_REPARSE_POINT
        ):
            raise OSError("Calibration directory must not be a link or reparse point")
        if not stat.S_ISDIR(directory_metadata.st_mode):
            raise OSError("Calibration directory must be a directory")

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
    provenance: CalibrationProvenance,
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
        "provenance": {
            "created_at_utc": _format_utc(provenance.created_at_utc),
            "primary_screen": {
                "left": provenance.primary_screen.left,
                "top": provenance.primary_screen.top,
                "width": provenance.primary_screen.width,
                "height": provenance.primary_screen.height,
            },
        },
        "validation": {
            "sample_count": validation.sample_count,
            "root_mean_square_error": validation.root_mean_square_error,
            "mean_error": validation.mean_error,
            "maximum_error": validation.maximum_error,
        },
    }


def _read_valid_envelope(
    path: Path,
    policy: CalibrationAcceptancePolicy,
) -> tuple[AcceptedCalibration, CalibrationProvenance, bytes]:
    metadata = path.lstat()
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    if (
        stat.S_ISLNK(metadata.st_mode)
        or attributes & _WINDOWS_REPARSE_POINT
        or not stat.S_ISREG(metadata.st_mode)
    ):
        raise OSError("Calibration envelope must be a regular non-link file")
    if metadata.st_size > MAXIMUM_CALIBRATION_FILE_BYTES:
        raise ValueError("Calibration file exceeds the 64 KiB limit")
    raw = path.read_bytes()
    if len(raw) > MAXIMUM_CALIBRATION_FILE_BYTES:
        raise ValueError("Calibration file exceeds the 64 KiB limit")
    document = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_json_constant,
    )
    fit_result, stored_policy, provenance = _decode_envelope(document)
    if stored_policy != policy:
        raise CalibrationPolicyMismatchError(
            "Stored calibration policy does not match the current policy; recalibrate."
        )
    acceptance = evaluate_calibration_acceptance(policy, fit_result.validation)
    if acceptance.state is not CalibrationAcceptanceState.ACCEPTED:
        raise ValueError("Stored calibration evidence no longer satisfies its policy")
    return AcceptedCalibration(fit_result, acceptance), provenance, raw


def _decode_envelope(
    document: object,
) -> tuple[CalibrationFitResult, CalibrationAcceptancePolicy, CalibrationProvenance]:
    envelope = _mapping(document, "Calibration envelope")
    _exact_keys(envelope, {"schema_version", "payload", "payload_sha256"}, "envelope")
    schema_version = _integer(envelope["schema_version"], "schema_version")
    if schema_version == 1:
        raise LegacyCalibrationSchemaError(
            "Stored calibration uses legacy schema 1 without display provenance; recalibrate."
        )
    if schema_version != CALIBRATION_ENVELOPE_SCHEMA_VERSION:
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
    _exact_keys(payload, {"mapper", "policy", "provenance", "validation"}, "payload")

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

    provenance_payload = _mapping(payload["provenance"], "Calibration provenance")
    _exact_keys(provenance_payload, {"created_at_utc", "primary_screen"}, "provenance")
    screen_payload = _mapping(provenance_payload["primary_screen"], "Primary screen provenance")
    _exact_keys(screen_payload, {"left", "top", "width", "height"}, "primary_screen")
    provenance = CalibrationProvenance(
        _parse_utc(provenance_payload["created_at_utc"]),
        PhysicalScreenGeometry(
            _integer(screen_payload["left"], "screen left"),
            _integer(screen_payload["top"], "screen top"),
            _integer(screen_payload["width"], "screen width"),
            _integer(screen_payload["height"], "screen height"),
        ),
    )
    return CalibrationFitResult(mapper, validation), policy, provenance


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Calibration creation time must be an ISO-8601 UTC value")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as error:
        raise ValueError("Calibration creation time is malformed") from error
    if _format_utc(parsed) != value:
        raise ValueError("Calibration creation time is not canonical")
    return parsed


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
