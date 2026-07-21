# Completed calibration pointer lifecycle

Date: 2026-07-22

## Summary

Fixed the state transition that could arm Live Input and immediately remove the accepted volatile
mapper. A completed Smooth Pursuit calibration now remains provisioned while Live Input is armed,
when the user leaves Calibration, and across camera pause/resume.

## Fixed

- Calibration page lifecycle hooks now cancel only an active countdown, collection, or retry state.
- `COMPLETE` is treated as accepted result state rather than in-progress volatile sampling.
- The Live Input arming callback can no longer call `cancel()`, clear the fit, emit a second empty
  provisioning update, and leave real input armed without a cursor pipeline.

## Verification

- Added a page regression covering arming, navigation, and tracking loss after completion.
- Strengthened the MainWindow activation test to start from `COMPLETE`, retain the accepted mapper
  and physical display geometry, accept a fresh gaze feature, and reach the pointer executor.
- Full deterministic suite: `822 passed`.
- Ruff, strict mypy, documentation link, and deterministic Windows icon checks passed.

## Known limitations

- Live pointer quality still depends on a fresh binocular gaze signal and the calibrated model;
  an armed state cannot compensate for unavailable face/iris observations.
- A newly started calibration intentionally replaces the prior volatile result.

## Next task

Repeat the physical flow from camera start through Smooth Pursuit, confirm Live Input, and verify
continuous pointer movement plus pause/resume on the target Windows display.
