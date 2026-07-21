# Direct live pointer activation after calibration

Date: 2026-07-22

## Summary

Removed the default `Review Required` dead end after a successful Smooth Pursuit calibration. Once
all nine regions, target-following correlation, and mapper fitting pass, MEYES now accepts the
mapper for the current session, provisions the cursor pipeline, and asks the user whether to
activate Live Input.

## Changed

- Added structurally validated completion acceptance when no stricter policy is configured.
- Kept explicitly configured four-limit policies as an optional stricter rejection and persistence
  boundary.
- Added a cancel-default **Calibration complete - activate Live Input?** dialog after successful
  cursor provisioning.
- Reused the existing Live Input controller so activation still requires Windows support, a running
  camera, global emergency-hotkey registration, physical-input preflight, and release-first arming.
- Kept a declined dialog in Safe Mode while leaving the accepted current-session pointer mapper
  ready for later activation from the Live Input page.
- Updated calibration, first-run, privacy, troubleshooting, judge, demo, submission, and todo copy.

## Verification

- Targeted calibration, presentation, Live Input, MainWindow, and first-run tests.
- Full deterministic test, Ruff, formatting, and strict mypy gates are recorded after completion of
  this iteration.

## Known limitations

- Completion acceptance is not a claim of universal physical-device accuracy.
- Without an explicit complete persistence policy, the accepted mapper is active only for the
  current application session and is not recovered after restart.
- Broad physical-device reach, 125%/150% scaling, and enabled High Contrast human QA remain pending.
