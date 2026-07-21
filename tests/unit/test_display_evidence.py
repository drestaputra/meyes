from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from meyes.cursor.screen_mapping import PhysicalScreenGeometry
from meyes.display_evidence import (
    CtypesWindowsSystemDpiReader,
    QtPrimaryScreenEvidence,
    capture_display_evidence,
    write_display_evidence,
)


@dataclass
class _GeometryProvider:
    geometry: PhysicalScreenGeometry
    reads: int = 0

    def read(self) -> PhysicalScreenGeometry:
        self.reads += 1
        return self.geometry


@dataclass
class _DpiReader:
    dpi: int
    reads: int = 0

    def read(self) -> int:
        self.reads += 1
        return self.dpi


def test_capture_reports_matching_logical_and_physical_geometry() -> None:
    geometry = _GeometryProvider(PhysicalScreenGeometry(0, 0, 1920, 1080))
    dpi = _DpiReader(120)

    evidence = capture_display_evidence(
        geometry,
        dpi,
        QtPrimaryScreenEvidence(0, 0, 1536, 864, 1.25),
        captured_at=datetime(2026, 7, 20, 12, 30, 15, 999, tzinfo=UTC),
    )

    assert evidence.captured_at_utc == "2026-07-20T12:30:15Z"
    assert evidence.reported_scale_percent == 125.0
    assert evidence.qt_scaled_size_matches_native
    assert evidence.qt_dpr_matches_reported_scale
    assert geometry.reads == 1
    assert dpi.reads == 1


def test_capture_marks_inconsistent_qt_scaling_without_hiding_values() -> None:
    evidence = capture_display_evidence(
        _GeometryProvider(PhysicalScreenGeometry(0, 0, 1920, 1080)),
        _DpiReader(144),
        QtPrimaryScreenEvidence(0, 0, 1920, 1080, 1.0),
        captured_at=datetime(2026, 7, 20, tzinfo=UTC),
    )

    assert evidence.reported_scale_percent == 150.0
    assert evidence.qt_scaled_size_matches_native
    assert not evidence.qt_dpr_matches_reported_scale


def test_evidence_writer_exclusively_creates_canonical_json(tmp_path: Path) -> None:
    evidence = capture_display_evidence(
        _GeometryProvider(PhysicalScreenGeometry(0, 0, 2560, 1440)),
        _DpiReader(96),
        QtPrimaryScreenEvidence(0, 0, 2560, 1440, 1.0),
        captured_at=datetime(2026, 7, 20, tzinfo=UTC),
    )
    output = tmp_path / "display" / "100-percent.json"

    written = write_display_evidence(output, evidence)

    document = json.loads(written.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert document["physical_primary_screen"]["width"] == 2560
    with pytest.raises(FileExistsError):
        write_display_evidence(output, evidence)


@pytest.mark.parametrize("dpi", [0, -1, True, 96.0])
def test_capture_rejects_invalid_dpi(dpi: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        capture_display_evidence(
            _GeometryProvider(PhysicalScreenGeometry(0, 0, 1920, 1080)),
            _DpiReader(dpi),  # type: ignore[arg-type]
            QtPrimaryScreenEvidence(0, 0, 1920, 1080, 1.0),
            captured_at=datetime(2026, 7, 20, tzinfo=UTC),
        )


def test_native_dpi_reader_rejects_unsupported_platform() -> None:
    with pytest.raises(OSError, match="only on Windows"):
        CtypesWindowsSystemDpiReader(platform_name="posix")
