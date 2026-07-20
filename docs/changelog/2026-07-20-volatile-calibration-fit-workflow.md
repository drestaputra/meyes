# 2026-07-20 - Volatile calibration fit workflow

## Summary

Connected a completed nine-point collection to the guarded quadratic mapper. Calibration now fits
only after every target reaches its bounded quota, displays deterministic held-out RMSE, mean,
maximum, and sample-count metrics, and reports unsafe numerical geometry as a recoverable retry.
The mapper remains memory-only and cannot move the operating-system pointer.

## Added

- A typed `CalibrationFitOutcome` with none, ready, and failed states.
- Automatic fit and deterministic validation after the ninth target completes.
- Visible volatile-mapper status and normalized holdout metrics in Calibration.
- Explicit retry feedback for incomplete-rank, ill-conditioned, or otherwise unsafe feature
  geometry without exposing low-level numerical details.
- Lifecycle clearing of both the mapper and its metrics on restart, cancellation, navigation away,
  tracking loss, Live Input arming, and shutdown.
- Controller and UI tests covering fit success, held-out metric rendering, numerical failure, and
  volatile-result erasure.

## Safety and quality decisions

- Collection completion is necessary but does not imply that the mapper is accepted for runtime
  control.
- The UI does not invent a universal pass/fail accuracy threshold before representative physical
  device evidence exists.
- A failed fit retains no mapper and gives the user a collection retry path.
- A successful fit is neither persisted nor activated, and no consumer connects it to
  `SendInput.move_pointer`.
- Holdout values are labeled as metrics from the current session, not as a cross-session accuracy
  guarantee.

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes\ui\calibration_controller.py src\meyes\ui\calibration_page.py tests\unit\test_calibration_ui.py
.\.venv\Scripts\python.exe -m mypy src\meyes\ui\calibration_controller.py src\meyes\ui\calibration_page.py tests\unit\test_calibration_ui.py
$env:QT_QPA_PLATFORM='offscreen'; .\.venv\Scripts\python.exe -m pytest -q tests\unit\test_calibration_ui.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 10 passed in 0.57 seconds.

Full repository gate:

- Ruff format: 115 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 115 source files.
- Native Windows pytest: 594 passed in 18.44 seconds.
- Native narrow-layout regression check: 4 passed in 2.09 seconds.

Visual QA:

- Rendered the successful-fit state at 1000 x 720 using the application stylesheet.
- Minimum page hint remained within 981 x 609 and the status, metrics, target grid, and actions did
  not overlap.
- The Qt `offscreen` plugin in this local environment could not load a font directory, so the full
  UI regression gate was intentionally verified on the target Windows native backend.

## Known limitations

- The current in-shell collection is not yet the distraction-free full-screen presentation.
- No evidence-based acceptance threshold or physical-device reach benchmark is defined yet.
- The mapper is not persisted, recovered, smoothed, converted to pixels, or used for pointer
  movement.
- Head-pose compensation and multi-monitor mapping remain pending.

## Next task

Add an explicit, evidence-backed acceptance boundary and safe mapper persistence/recovery without
weakening the session-only Live Input safety contract.
