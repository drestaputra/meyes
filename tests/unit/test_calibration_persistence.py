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
    MAXIMUM_DELETED_CALIBRATION_BACKUPS,
    AcceptedCalibrationRepository,
    CalibrationProvenance,
)
from meyes.cursor.screen_mapping import PhysicalScreenGeometry
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


def _provenance() -> CalibrationProvenance:
    return CalibrationProvenance(
        datetime(2026, 7, 20, 8, 15, tzinfo=UTC),
        PhysicalScreenGeometry(0, 0, 1920, 1080),
    )


def test_round_trip_recovers_proof_under_exact_policy(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    expected = _calibration()

    path = repository.save(expected, _policy(), _provenance())
    result = repository.load(_policy())

    assert path == repository.path
    assert result.calibration == expected
    assert result.provenance == _provenance()
    assert result.warning is None
    document = json.loads(path.read_text(encoding="utf-8"))
    assert set(document) == {"schema_version", "payload", "payload_sha256"}
    assert set(document["payload"]) == {"mapper", "policy", "provenance", "validation"}
    serialized = path.read_text(encoding="utf-8")
    assert "raw_samples" not in serialized
    assert "capture_timestamp" not in serialized
    assert "source_sequence" not in serialized


def test_no_runtime_policy_does_not_read_or_move_stored_file(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    repository.save(_calibration(), _policy(), _provenance())
    original = repository.path.read_bytes()

    result = repository.load(None)

    assert result.calibration is None
    assert "no policy" in (result.warning or "")
    assert repository.path.read_bytes() == original
    assert result.recovered_from is None


def test_policy_change_requires_recalibration_without_quarantine(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    repository.save(_calibration(), _policy(), _provenance())

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
    repository.save(_calibration(), _policy(), _provenance())
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
        repository.save(_calibration(), _policy(maximum_error=0.03), _provenance())

    assert not repository.path.exists()


def test_failed_atomic_replace_preserves_previous_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    repository.save(_calibration(), _policy(), _provenance())
    original = repository.path.read_bytes()

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("replace unavailable")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace unavailable"):
        repository.save(_calibration(), _policy(), _provenance())

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


def test_legacy_schema_is_preserved_but_never_recovered(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    legacy = '{"schema_version":1,"payload":{},"payload_sha256":"' + "0" * 64 + '"}'
    paths.calibration_file.write_text(legacy, encoding="utf-8")

    result = AcceptedCalibrationRepository(paths).load(_policy())

    assert result.calibration is None
    assert "legacy schema 1" in (result.warning or "")
    assert result.recovered_from is None
    assert paths.calibration_file.read_text(encoding="utf-8") == legacy


def test_provenance_requires_utc_creation_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        CalibrationProvenance(
            datetime(2026, 7, 20, 8, 15),
            PhysicalScreenGeometry(0, 0, 1920, 1080),
        )


def test_forget_moves_envelope_to_recoverable_timestamped_backup(tmp_path: Path) -> None:
    fixed_now = datetime(2026, 7, 20, 10, 45, tzinfo=UTC)
    repository = AcceptedCalibrationRepository(
        AppPaths.under(tmp_path),
        clock=lambda: fixed_now,
    )
    repository.save(_calibration(), _policy(), _provenance())
    original = repository.path.read_bytes()

    backup = repository.forget()

    assert backup is not None
    assert backup.name.startswith("accepted-calibration.deleted-20260720-104500")
    assert backup.read_bytes() == original
    assert not repository.path.exists()
    assert repository.forget() is None


def test_deleted_catalog_is_bounded_newest_first_and_read_only(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    total = MAXIMUM_DELETED_CALIBRATION_BACKUPS + 2
    for index in range(total):
        stamp = f"20260720-1045{index:02d}-000000"
        (paths.data_dir / f"accepted-calibration.deleted-{stamp}.json").write_bytes(
            f"backup-{index}".encode()
        )
    malformed = paths.data_dir / "accepted-calibration.deleted-unknown.json"
    malformed.write_text("keep", encoding="utf-8")
    repository = AcceptedCalibrationRepository(paths)

    catalog = repository.deleted_catalog()

    assert len(catalog.backups) == MAXIMUM_DELETED_CALIBRATION_BACKUPS
    assert catalog.backups[0].deleted_at_utc > catalog.backups[-1].deleted_at_utc
    assert catalog.backups[0].size_bytes > 0
    assert catalog.warning is not None
    assert malformed.read_text(encoding="utf-8") == "keep"


def test_deleted_catalog_does_not_follow_backup_symlink(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    sentinel = tmp_path / "outside.json"
    sentinel.write_text("keep", encoding="utf-8")
    link = paths.data_dir / "accepted-calibration.deleted-20260720-104500-000000.json"
    try:
        link.symlink_to(sentinel)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable: {error}")

    catalog = AcceptedCalibrationRepository(paths).deleted_catalog()

    assert catalog.backups == ()
    assert catalog.warning is not None
    assert link.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_restore_exclusively_reactivates_valid_backup_and_retains_copy(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    expected = _calibration()
    repository.save(expected, _policy(), _provenance())
    deleted = repository.forget()
    assert deleted is not None
    backup = repository.deleted_catalog().backups[0]
    deleted_bytes = deleted.read_bytes()

    result = repository.restore(backup, _policy())

    assert result.calibration == expected
    assert result.provenance == _provenance()
    assert repository.path.read_bytes() == deleted_bytes
    assert deleted.read_bytes() == deleted_bytes


def test_restore_never_replaces_an_active_envelope(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    repository.save(_calibration(), _policy(), _provenance())
    deleted = repository.forget()
    assert deleted is not None
    backup = repository.deleted_catalog().backups[0]
    repository.save(_calibration(), _policy(), _provenance())
    active = repository.path.read_bytes()

    with pytest.raises(FileExistsError, match="already exists"):
        repository.restore(backup, _policy())

    assert repository.path.read_bytes() == active
    assert deleted.exists()


def test_restore_keeps_tampered_backup_inactive(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    repository.save(_calibration(), _policy(), _provenance())
    deleted = repository.forget()
    assert deleted is not None
    document = json.loads(deleted.read_text(encoding="utf-8"))
    document["payload"]["mapper"]["horizontal_coefficients"][1] = 9.0
    deleted.write_text(json.dumps(document), encoding="utf-8")
    backup = repository.deleted_catalog().backups[0]

    result = repository.restore(backup, _policy())

    assert result.calibration is None
    assert "checksum" in (result.warning or "")
    assert not repository.path.exists()
    assert deleted.exists()


def test_restore_requires_exact_current_catalog_record(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    repository.save(_calibration(), _policy(), _provenance())
    deleted = repository.forget()
    assert deleted is not None
    backup = repository.deleted_catalog().backups[0]
    stale_metadata = type(backup)(backup.path, backup.deleted_at_utc, backup.size_bytes + 1)

    with pytest.raises(ValueError, match="exact current catalog record"):
        repository.restore(stale_metadata, _policy())

    assert not repository.path.exists()
    assert deleted.exists()


def test_restore_is_disabled_without_runtime_policy(tmp_path: Path) -> None:
    repository = AcceptedCalibrationRepository(AppPaths.under(tmp_path))
    repository.save(_calibration(), _policy(), _provenance())
    deleted = repository.forget()
    assert deleted is not None
    backup = repository.deleted_catalog().backups[0]

    result = repository.restore(backup, None)

    assert result.calibration is None
    assert "no policy" in (result.warning or "")
    assert not repository.path.exists()
    assert deleted.exists()
