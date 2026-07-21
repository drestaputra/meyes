# 2026-07-21 - First-run orientation

## Summary

Activated the existing durable `first_run` configuration boundary with a three-step native
orientation dialog shown after the main window opens on a new profile.

## Safety behavior

- The wizard explains local processing, intentional non-persistence, responsible capture, camera
  permission, diagnostics, calibration `Review Required`, exact Live Input consent, and emergency
  release.
- It never enumerates/opens a camera, constructs a vision model or `SendInput`, registers a hotkey,
  or changes Live Input state.
- `Not now` closes the dialog without marking setup complete, so it returns next launch.
- Finish remains disabled until the user selects the explicit Live Input safety acknowledgement.
- Completion is accepted only after `first_run=false` is saved atomically; persistence failure keeps
  the wizard open and reports that MEYES remains in Safe Mode.
- Direct `MainWindow` construction has no dialog side effect; the application composition root opens
  it after the window is visible.

## Verification

- Three wizard tests cover step navigation, acknowledgement gating, Not now, successful completion,
  and persistence failure.
- MainWindow integration proves completion persistence while camera remains Stopped and Live Input
  remains Safe.
- Native 720x560 visual QA confirmed the locked canvas/surface/focus/primary-action tokens.
- Ruff formatting/lint and strict mypy passed across 150 source files; all 768 tests passed on native
  Windows Qt.
