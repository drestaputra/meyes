"""Generate or verify deterministic Windows icon assets from the canonical SVG."""

from __future__ import annotations

import argparse
import hashlib
import os
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SVG = REPOSITORY_ROOT / "resources" / "icons" / "meyes.svg"
DEFAULT_ICO = REPOSITORY_ROOT / "resources" / "icons" / "meyes.ico"


def _render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter, QRectF(0, 0, size, size))
    finally:
        painter.end()

    encoded = QByteArray()
    buffer = QBuffer(encoded)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Could not open the in-memory PNG buffer")
    try:
        if not image.save(buffer, "PNG"):
            raise RuntimeError(f"Could not encode the {size}px icon frame")
    finally:
        buffer.close()
    return bytes(encoded)


def build_windows_icon(svg_path: Path) -> bytes:
    """Return a Windows ICO containing PNG frames for every supported source size."""
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise ValueError(f"Invalid SVG icon source: {svg_path}")

    frames = [(size, _render_png(renderer, size)) for size in ICON_SIZES]
    directory_size = 6 + 16 * len(frames)
    entries = bytearray()
    payload = bytearray()
    offset = directory_size
    for size, frame in frames:
        dimension = 0 if size == 256 else size
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(frame),
                offset,
            )
        )
        payload.extend(frame)
        offset += len(frame)
    return struct.pack("<HHH", 0, 1, len(frames)) + bytes(entries) + bytes(payload)


def _write_atomically(output_path: Path, content: bytes) -> None:
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_bytes(content)
    os.replace(temporary_path, output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg", type=Path, default=DEFAULT_SVG)
    parser.add_argument("--output", type=Path, default=DEFAULT_ICO)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the derived ICO; otherwise verify that the committed file matches",
    )
    arguments = parser.parse_args()

    expected = build_windows_icon(arguments.svg)
    digest = hashlib.sha256(expected).hexdigest()
    if arguments.write:
        _write_atomically(arguments.output, expected)
        print(f"Wrote {arguments.output} ({len(expected)} bytes, sha256={digest})")
        return 0

    if not arguments.output.is_file():
        parser.error(f"derived icon is missing: {arguments.output}; rerun with --write")
    actual = arguments.output.read_bytes()
    if actual != expected:
        parser.error(
            f"derived icon does not match {arguments.svg}; rerun with --write "
            f"(expected sha256={digest})"
        )
    print(f"WINDOWS ICON VERIFICATION: PASSED ({len(expected)} bytes, sha256={digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
