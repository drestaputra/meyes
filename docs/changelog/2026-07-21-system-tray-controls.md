# 2026-07-21 - System tray controls

## Summary

Added optional system-tray controls composed only when the desktop reports tray availability. The
tray mirrors existing camera and Live Input state rather than creating a second lifecycle owner.

## Behavior

- Status row distinguishes Safe Mode, Live Input, Live Input fault/closed, and camera lifecycle.
- Show restores, raises, and activates the main window.
- One tracking action is enabled only for Running/Pause and maps to the existing controller.
- Return to Safe Mode is enabled only for Armed/Faulted and uses the normal release-first disarm.
- Quit invokes the normal main-window close path.
- Main-window close hides/disables the tray before closing calibration, input, vision, and camera
  resources; close-to-tray/background execution is intentionally not introduced.
- Production constructs/shows the icon only after `QSystemTrayIcon.isSystemTrayAvailable()` passes;
  unit tests keep the icon hidden.

## Verification

- Two tray tests cover state/action mapping, pause/resume/Safe callbacks, single/double-click Show,
  Quit, and idempotent close with the test icon hidden.
- Nineteen MainWindow lifecycle tests passed with the optional controller integrated.
- Ruff formatting/lint and strict mypy passed across 152 source files; all 770 tests passed on native
  Windows Qt.
