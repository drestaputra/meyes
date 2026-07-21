# 2026-07-21 - Keyboard shell navigation

## Summary

Added direct keyboard page switching and durable selected-page state to the native shell without
changing camera, calibration, or Live Input lifecycle state.

## Behavior

- The existing navigation list supports Up/Down arrow selection.
- Ctrl+1 through Ctrl+9 select Dashboard through Privacy in visible navigation order.
- Direct shortcuts return keyboard focus to the navigation list, whose theme has an explicit focus
  border.
- Every valid selection updates the stacked page immediately.
- Selected-page persistence is atomic through the existing config manager; write failure is logged
  and leaves the prior durable preference intact.
- Invalid internal row requests fail before changing focus or selection.

## Verification

- Eighteen MainWindow tests include native Qt arrow-key switching, stacked-page parity, the exact
  Ctrl+9 shortcut, focus return, and persisted Calibration/Privacy selections.
- Ruff formatting/lint and strict mypy passed across 148 source files; all 764 tests passed on native
  Windows Qt.

Native file-dialog and full-screen calibration keyboard behavior still requires a human end-to-end
pass and remains explicitly pending.
