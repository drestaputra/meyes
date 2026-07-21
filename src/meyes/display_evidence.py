"""Read-only Windows display-scaling evidence capture."""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from meyes.cursor.screen_mapping import PhysicalScreenGeometry, PhysicalScreenGeometryProvider
from meyes.cursor.windows_geometry import WindowsPrimaryScreenGeometryProvider

_BASE_WINDOWS_DPI = 96


@runtime_checkable
class WindowsSystemDpiReader(Protocol):
    """Read the Windows system DPI without changing display configuration."""

    def read(self) -> int: ...


class CtypesWindowsSystemDpiReader:
    """Narrow read-only `GetDpiForSystem` adapter."""

    def __init__(self, *, platform_name: str | None = None) -> None:
        selected_platform = os.name if platform_name is None else platform_name
        if selected_platform != "nt":
            raise OSError("Windows system DPI is available only on Windows")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        try:
            get_dpi_for_system: Any = user32.GetDpiForSystem
        except AttributeError as error:
            raise OSError("GetDpiForSystem is unavailable") from error
        get_dpi_for_system.argtypes = ()
        get_dpi_for_system.restype = ctypes.c_uint
        self._get_dpi_for_system = get_dpi_for_system

    def read(self) -> int:
        dpi = int(self._get_dpi_for_system())
        if dpi <= 0:
            error_code = ctypes.get_last_error()
            raise OSError(error_code, "Windows system DPI read failed")
        return dpi


@dataclass(frozen=True, slots=True)
class QtPrimaryScreenEvidence:
    """Qt's logical primary-screen view and device-pixel ratio."""

    left: int
    top: int
    width: int
    height: int
    device_pixel_ratio: float

    def __post_init__(self) -> None:
        for name, value in (
            ("left", self.left),
            ("top", self.top),
            ("width", self.width),
            ("height", self.height),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"Qt screen {name} must be an integer")
        if self.width < 1 or self.height < 1:
            raise ValueError("Qt screen dimensions must be positive")
        if (
            isinstance(self.device_pixel_ratio, bool)
            or not isinstance(self.device_pixel_ratio, (int, float))
            or not math.isfinite(self.device_pixel_ratio)
            or self.device_pixel_ratio <= 0
        ):
            raise ValueError("Qt device-pixel ratio must be finite and positive")


@dataclass(frozen=True, slots=True)
class WindowsDisplayEvidence:
    """One timestamped, non-mutating display configuration observation."""

    captured_at_utc: str
    system_dpi: int
    reported_scale_percent: float
    physical_primary_screen: PhysicalScreenGeometry
    qt_primary_screen: QtPrimaryScreenEvidence
    qt_scaled_size_matches_native: bool
    qt_dpr_matches_reported_scale: bool

    def to_document(self) -> dict[str, object]:
        document = asdict(self)
        document["schema_version"] = 1
        return document


def capture_display_evidence(
    geometry_provider: PhysicalScreenGeometryProvider,
    dpi_reader: WindowsSystemDpiReader,
    qt_screen: QtPrimaryScreenEvidence,
    *,
    captured_at: datetime | None = None,
) -> WindowsDisplayEvidence:
    """Capture one deterministic evidence record without changing OS state."""

    if not isinstance(geometry_provider, PhysicalScreenGeometryProvider):
        raise TypeError("Expected PhysicalScreenGeometryProvider")
    if not isinstance(dpi_reader, WindowsSystemDpiReader):
        raise TypeError("Expected WindowsSystemDpiReader")
    if not isinstance(qt_screen, QtPrimaryScreenEvidence):
        raise TypeError("Expected QtPrimaryScreenEvidence")
    timestamp = datetime.now(UTC) if captured_at is None else captured_at
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise ValueError("Evidence capture time must be timezone-aware")
    physical = geometry_provider.read()
    if not isinstance(physical, PhysicalScreenGeometry):
        raise TypeError("Geometry provider returned an invalid result")
    dpi = dpi_reader.read()
    if isinstance(dpi, bool) or not isinstance(dpi, int) or dpi <= 0:
        raise ValueError("System DPI must be a positive integer")
    scale_percent = dpi / _BASE_WINDOWS_DPI * 100.0
    expected_width = round(qt_screen.width * qt_screen.device_pixel_ratio)
    expected_height = round(qt_screen.height * qt_screen.device_pixel_ratio)
    return WindowsDisplayEvidence(
        timestamp.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        dpi,
        scale_percent,
        physical,
        qt_screen,
        expected_width == physical.width and expected_height == physical.height,
        math.isclose(
            qt_screen.device_pixel_ratio,
            dpi / _BASE_WINDOWS_DPI,
            rel_tol=0.0,
            abs_tol=0.01,
        ),
    )


def write_display_evidence(path: Path, evidence: WindowsDisplayEvidence) -> Path:
    """Exclusively create one JSON evidence file without replacing prior evidence."""

    if not isinstance(path, Path):
        raise TypeError("Expected Path")
    if not isinstance(evidence, WindowsDisplayEvidence):
        raise TypeError("Expected WindowsDisplayEvidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evidence.to_document(), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """Capture the current primary display to a caller-selected new JSON file."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance()
    if not isinstance(application, QGuiApplication):
        application = QGuiApplication([])
    screen = application.primaryScreen()
    if screen is None:
        raise RuntimeError("Qt did not report a primary screen")
    logical = screen.geometry()
    qt_screen = QtPrimaryScreenEvidence(
        logical.left(),
        logical.top(),
        logical.width(),
        logical.height(),
        float(screen.devicePixelRatio()),
    )
    evidence = capture_display_evidence(
        WindowsPrimaryScreenGeometryProvider(),
        CtypesWindowsSystemDpiReader(),
        qt_screen,
    )
    output = write_display_evidence(arguments.output, evidence)
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
