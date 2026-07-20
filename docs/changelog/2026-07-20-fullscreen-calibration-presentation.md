# 2026-07-20 - Full-screen calibration presentation

## Summary

Promoted the guided nine-point collection into a distraction-free primary-display presentation.
The active target is placed at its normalized 10%, 50%, or 90% screen coordinate, while a compact
header and footer expose instructions, progress, fit feedback, and explicit controls. The same
bounded controller and volatile safety lifecycle remain authoritative.

## Added

- A dedicated top-level `CalibrationPresentation` using the primary screen's full geometry.
- A visible 32-pixel focus marker placed from the current target's normalized screen coordinate.
- Space to begin capture, Enter to advance, R to retry, and Escape to cancel.
- Compact full-screen progress, rejection feedback, final fit/acceptance status, and an explicit
  Return to Calibration action after completion.
- Automatic presentation closure after controller cancellation from tracking loss, navigation,
  Live Input arming, reset, or shutdown.
- Window-close cancellation that clears samples and fit state instead of allowing hidden capture.
- Native theme roles for the full-screen canvas, instruction strip, footer, and focus marker.
- Qt tests for target placement, keyboard progression, external cancellation, Escape, window close,
  and completion-return preservation.

## Safety and quality decisions

- The page still releases Live Input before a collection can start.
- Closing or escaping the presentation cancels the controller and erases volatile data; only the
  explicit completion-return action preserves a completed volatile fit for review in the page.
- Collection never continues behind a hidden presentation.
- Primary-display presentation does not imply calibrated pixel mapping or pointer activation.
- The fallback in-shell controls remain available for accessibility and deterministic testing.

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes\ui\calibration_presentation.py src\meyes\ui\calibration_page.py src\meyes\ui\theme.py tests\unit\test_calibration_presentation.py tests\unit\test_calibration_ui.py
.\.venv\Scripts\python.exe -m mypy src\meyes\ui\calibration_presentation.py src\meyes\ui\calibration_page.py src\meyes\ui\theme.py tests\unit\test_calibration_presentation.py tests\unit\test_calibration_ui.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_calibration_presentation.py tests\unit\test_calibration_ui.py tests\unit\test_main_window.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 27 passed in 4.61 seconds.

Full repository gate:

- Ruff format: 119 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 119 source files.
- Native Windows pytest: 618 passed in 15.84 seconds.

## Visual QA

- Rendered the top-left awaiting-target state at 1200 x 760 on native Windows Qt.
- Target center was `(119, 75)` pixels versus the integer-geometry expectation near `(120, 76)`.
- Header, target, empty canvas, progress, keyboard actions, and cancellation control were readable
  without overlap.

## Known limitations

- Only the primary display is presented; multi-monitor calibration remains deferred.
- The header/footer occupy a small overlay region near the screen edges.
- There is no spoken cue, countdown, or dwell-to-capture option yet.
- Physical reach evidence, mapper persistence, smoothing, and pointer output remain pending.

## Next task

Add a deterministic adaptive cursor-smoothing domain pipeline and replay tests without connecting it
to the operating-system pointer.
