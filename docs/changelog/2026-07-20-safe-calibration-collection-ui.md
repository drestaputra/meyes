# 2026-07-20 - Safe calibration collection UI

## Summary

Connected the bounded nine-point collector to a native Calibration page. Users can start a
volatile session, explicitly capture one target at a time, inspect progress, retry failed targets,
and cancel safely. This iteration does not fit or persist a mapping and cannot move the pointer.

## Added

- A Qt-owned calibration controller consuming serialized normalized-gaze features.
- A nine-point visual map, `Point n of 9` progress, accepted-sample progress, and factual status.
- Explicit Start, Capture current point, Next/Retry, and Cancel controls.
- Tracking-availability gating and inline rejection feedback.
- Calibration page wiring in the stable main navigation.

## Safety decisions

- Starting collection first disarms Live Input; failure to release blocks the session.
- Collection is never implicit: each target waits for the user to choose Capture.
- Escape, navigation away, camera/tracking loss, Live Input arming, cancel, restart, and application
  close discard every volatile sample.
- Live Input may still be armed from its dedicated page, but doing so immediately cancels any
  calibration collection before further gaze samples are accepted.
- The page states that collection does not fit, save, or execute a pointer mapping.

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes\ui\calibration_controller.py src\meyes\ui\calibration_page.py src\meyes\ui\main_window.py tests\unit\test_calibration_ui.py tests\unit\test_main_window.py
.\.venv\Scripts\python.exe -m mypy src\meyes\ui\calibration_controller.py src\meyes\ui\calibration_page.py src\meyes\ui\main_window.py tests\unit\test_calibration_ui.py tests\unit\test_main_window.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_calibration_ui.py tests\unit\test_main_window.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 15 passed in 4.53 seconds.

Full repository gate:

- Ruff format: 111 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 111 source files.
- Pytest: 572 passed in 16.41 seconds.

## Native QA

- Native Windows themed render: passed at 1200 x 760 with the complete target map, progress,
  status, and controls visible without horizontal overflow.
- The render used a synthetic session and did not activate camera/model backends, a hotkey, or
  `SendInput`.

## Known limitations

- Collection remains inside the application shell rather than using the planned distraction-free
  full-screen target presentation.
- Statistical outlier rejection, mapper fitting, validation scoring, persistence, smoothing, and
  pointer output remain pending.

## Next task

Add deterministic per-target statistical outlier rejection and a replaceable calibration mapper,
keeping all operating-system pointer output dormant.
