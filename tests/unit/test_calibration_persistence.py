from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from meyes.calibration.acceptance import (
    AcceptedCalibration,
    CalibrationAcceptance,
    CalibrationAcceptancePolicy,
    CalibrationAcceptanceState,
)
from meyes.calibration.mapper import (
    CalibrationFitResult,
    CalibrationValidation,
    PolynomialCalibrationMapper,
)
from meyes.calibration.persistence import (
    MAXIMUM_CALIBRATION_FILE_BYTES,
    AcceptedCalibrationRepository,
)
from meyes.util.paths import AppPaths


def _policy(*, maximum_error: float = 0.1) -> CalibrationAcceptancePolicy:
    return CalibrationAcceptancePolicy(0.05, 0.04, maximum_error, 18)


def _calibration() -> AcceptedCalibration:
    mapper = PolynomialCalibrationMapper(
        (0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0, 0.0, 0.0),
    )
    fit = CalibrationFitResult(mapper, CalibrationValidation(18, 0.02, 0.015, 0.04))
    return AcceptedCalibration(
        fit,
        CalibrationAcceptance(CalibrationAcceptanceState.ACCEPTED),
    )


def test_round_trip_recovers_proof_under_exact_policy(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    expected = _calibration()

    path = repository.save(expected, _policy())
    result = repository.load(_policy())

    assert path == repository.path
    assert result.calibration == expected
    assert result.warning is None
    document = json.loads(path.read_text(encoding="utf-8"))
    assert set(document) == {"schema_version", "payload", "payload_sha256"}
    assert set(document["payload"]) == {"mapper", "policy", "validation"}
    serialized = path.read_text(encoding="utf-8")
    assert "raw_samples" not in serialized
    assert "capture_timestamp" not in serialized
    assert "source_sequence" not in serialized


def test_no_runtime_policy_does_not_read_or_move_stored_file(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    repository.save(_calibration(), _policy())
    original = repository.path.read_bytes()

    result = repository.load(None)

    assert result.calibration is None
    assert "no policy" in (result.warning or "")
    assert repository.path.read_bytes() == original
    assert result.recovered_from is None


def test_policy_change_requires_recalibration_without_quarantine(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    repository.save(_calibration(), _policy())

    result = repository.load(_policy(maximum_error=0.09))

    assert result.calibration is None
    assert "does not match" in (result.warning or "")
    assert repository.path.exists()
    assert result.recovered_from is None


def test_checksum_tampering_is_quarantined_and_never_recovers(tmp_path: Path) -> None:
    fixed_now = datetime(2026, 7, 20, 9, 30, tzinfo=UTC)
    repository = AcceptedCalibrationRepository(
        AppPaths.under(tmp_path),
        clock=lambda: fixed_now,
    )
    repository.save(_calibration(), _policy())
    document = json.loads(repository.path.read_text(encoding="utf-8"))
    document["payload"]["mapper"]["horizontal_coefficients"][1] = 9.0
    repository.path.write_text(json.dumps(document), encoding="utf-8")

    result = repository.load(_policy())

    assert result.calibration is None
    assert "checksum" in (result.warning or "")
    assert result.recovered_from is not None
    assert result.recovered_from.name.startswith("accepted-calibration.invalid-20260720-093000")
    assert not repository.path.exists()


@pytest.mark.parametrize(
    "document",
    [
        '{"schema_version":1,"schema_version":1}',
        '{"schema_version":NaN}',
        '{"schema_version":2,"payload":{},"payload_sha256":"' + "0" * 64 + '"}',
        '{"schema_version":1,"payload":{},"payload_sha256":"bad"}',
    ],
)
def test_ambiguous_or_malformed_documents_fail_closed(tmp_path: Path, document: str) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    paths.calibration_file.write_text(document, encoding="utf-8")
    repository = AcceptedCalibrationRepository(paths)

    result = repository.load(_policy())

    assert result.calibration is None
    assert result.warning is not None


def test_oversized_document_fails_closed_before_json_decode(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    paths.calibration_file.write_bytes(b"{" + b" " * MAXIMUM_CALIBRATION_FILE_BYTES + b"}")

    result = AcceptedCalibrationRepository(paths).load(_policy())

    assert result.calibration is None
    assert "64 KiB" in (result.warning or "")


def test_save_rejects_evidence_that_does_not_satisfy_policy(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))

    with pytest.raises(ValueError, match="does not satisfy"):
        repository.save(_calibration(), _policy(maximum_error=0.03))

    assert not repository.path.exists()


def test_failed_atomic_replace_preserves_previous_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    repository.save(_calibration(), _policy())
    original = repository.path.read_bytes()

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("replace unavailable")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace unavailable"):
        repository.save(_calibration(), _policy())

    assert repository.path.read_bytes() == original
    assert list(repository.path.parent.glob(".accepted-calibration-*.tmp")) == []


def test_load_does_not_follow_or_quarantine_calibration_symlink(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    sentinel = tmp_path / "outside.json"
    sentinel.write_text('{"keep":true}', encoding="utf-8")
    try:
        paths.calibration_file.symlink_to(sentinel)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")

    result = AcceptedCalibrationRepository(paths).load(_policy())

    assert result.calibration is None
    assert "link or reparse" in (result.warning or "")
    assert result.recovered_from is None
    assert paths.calibration_file.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == '{"keep":true}'
