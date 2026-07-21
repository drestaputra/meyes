# 2026-07-21 - Calibrated Live Input pointer

## Summary

Connected accepted, display-matched gaze cursor candidates to real Windows pointer movement while
preserving Safe Mode before camera startup. The cursor-domain pipeline remains executor-independent;
its pixel candidates cross into `WindowsSendInputExecutor` only while the volatile Live Input
controller is armed.

Camera startup remains in Safe Mode. Every arm requires the exact typed phrase; manual disarm,
profile changes, calibration, file dialogs, camera pause/fault, and emergency stop release input
and require fresh consent before another arm.

## Added

- Absolute `MOUSEINPUT` packets with calibrated primary-screen pixels normalized to `0..65535`.
- Lazy, cached physical primary-screen geometry validation at the native executor boundary.
- A cursor-candidate Qt signal and an armed-only Live Input pointer slot.
- Explicit-consent-only arming after the camera reaches `Running`, followed by emergency-hotkey,
  physical-input, and release-first preflights.
- Fail-closed pointer errors that gate dispatch, release input owned by MEYES, retain the emergency
  hotkey for recovery, and request tracking pause.
- Deterministic native-boundary, controller, and composition-root tests that never move the real
  test-machine pointer.

## Changed

- Live Input now describes calibrated gaze movement alongside click, scroll, and keyboard output.
- Cursor and calibration status copy now distinguishes executor-independent candidate production
  from the explicit Live Input output gate.

## Verification

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m mypy src tests
.\.venv\Scripts\python.exe -m pytest -q
```

Focused formatting, lint, typing, and tests passed. The full deterministic suite passed with
`719 passed`.

## Known limitations

- Pointer output is primary-monitor only and requires an accepted calibration matching the current
  physical primary-display geometry.
- Broad physical-device reach and Windows 100%, 125%, and 150% scaling still require manual QA.
- Windows can block `SendInput` across integrity levels; MEYES does not bypass UIPI.

## Next task

Collect representative physical-device reach evidence and use it to justify calibration acceptance
thresholds before broader pointer-output claims.
