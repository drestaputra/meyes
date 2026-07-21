"""Record one Windows application window to an MP4 file.

This helper is intentionally small and local-only.  It captures the rectangle of
an already-open top-level window and stops cleanly when a sentinel file appears.
"""

from __future__ import annotations

import argparse
import ctypes
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import ImageGrab


class Rect(ctypes.Structure):
    """Win32 RECT structure."""

    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def window_bounds(hwnd: int) -> tuple[int, int, int, int]:
    """Return the current screen-space bounds for ``hwnd``."""

    rect = Rect()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise OSError(f"GetWindowRect failed for HWND {hwnd}")
    if rect.right <= rect.left or rect.bottom <= rect.top:
        raise ValueError(f"Window {hwnd} has invalid bounds: {rect!r}")
    return rect.left, rect.top, rect.right, rect.bottom


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hwnd", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stop-file", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--max-seconds", type=float, default=240.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bounds = window_bounds(args.hwnd)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    width -= width % 2
    height -= height % 2
    if width < 2 or height < 2:
        raise ValueError(f"Window {args.hwnd} is too small to record")

    writer = cv2.VideoWriter(
        str(args.output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        args.fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not open MP4 writer for {args.output}")

    frame_interval = 1.0 / args.fps
    started_at = time.perf_counter()
    next_frame_at = started_at
    frames_written = 0
    try:
        while not args.stop_file.exists():
            now = time.perf_counter()
            if now - started_at >= args.max_seconds:
                break
            if now < next_frame_at:
                time.sleep(min(next_frame_at - now, 0.01))
                continue

            current = window_bounds(args.hwnd)
            bbox = (
                current[0],
                current[1],
                current[0] + width,
                current[1] + height,
            )
            image = np.asarray(ImageGrab.grab(bbox=bbox, all_screens=True))
            writer.write(cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            frames_written += 1
            next_frame_at = started_at + frames_written * frame_interval
    finally:
        writer.release()

    elapsed = time.perf_counter() - started_at
    print(
        f"Recorded {frames_written} frames at {width}x{height} in {elapsed:.2f}s to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
