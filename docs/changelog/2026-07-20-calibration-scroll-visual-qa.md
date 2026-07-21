# 2026-07-20 - Calibration scroll visual QA

## Summary

Native Windows rendering revealed vertical compression after the persistence controls were added:
fit rows disappeared, target labels overlapped, and action buttons collided at minimum height. The
Calibration content now uses a vertical-only native scroll area that preserves every control's size
hint.

## Changed

- Wrapped the complete Calibration content in a resizable, frameless `QScrollArea`.
- Explicitly disabled horizontal scrolling while retaining vertical access at constrained heights.
- Replaced the deleted-backup metadata middle dot with an ASCII separator for font consistency.
- Added an automated minimum-viewport invariant covering vertical scroll and retained control heights.

## Visual QA

Native screenshots were rendered and inspected at:

- 900 x 640, top and bottom scroll positions;
- 1200 x 760, top and bottom scroll positions.

The final render has no target/control overlap or horizontal scrollbar. The minimum window exposes
the remaining form and persistence controls through vertical scrolling; the target window preserves
comfortable grid, form, confirmation, and action spacing.

## Verification

Focused Ruff and strict mypy passed; 14 Calibration UI tests passed in 2.24 seconds.

Full repository gate:

- Ruff format: 138 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 138 source files.
- Native Windows pytest: 720 passed in 23.22 seconds.

## Known limitations

- Native scrollbar appearance follows the current Windows/Qt style.
- High-contrast and 125%/150% Windows scaling visual QA remain pending.
- Scaling-matrix physical-device calibration evidence and gaze pointer output remain pending.

## Next task

Run Windows 125% and 150% scaling layout verification, beginning with programmatic DPI/geometry
evidence and native Calibration/Diagnostics screenshots where the host supports those scale modes.
