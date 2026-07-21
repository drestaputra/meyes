# 2026-07-21 - Cross-page design review

## Summary

Reviewed the implemented PySide6 shell and all nine navigation pages against the Hallmark-inspired
`DESIGN.md` gate. Corrected stale design/runtime controls and a minimum-size Dashboard overlap.

## Changes

- Replaced the permanently disabled `Resume tracking`/Phase 1 top-bar placeholder with explicit
  camera status and contextual Open Dashboard, Pause camera, or Resume camera behavior.
- Kept the top camera state separate from the persistent Safe/Live Input boundary; camera commands
  never arm operating-system input.
- Reduced only the preview's internal minimum from 480×320 to 320×240 so the Dashboard remains
  non-overlapping at the application's supported 900×640 minimum and still expands at larger sizes.
- Updated the design implementation boundary, emergency shortcut, minimum size, current
  deliverables, honest pending human checks, and evidence-based Hallmark review score.

## Verification

- Added top-bar lifecycle/action/accessibility tests and a 900×640 geometry regression test.
- MainWindow focused suite: 23 passed.
- Native top-state renders: all nine pages at 900×640 and 1200×760.
- Native bottom-state renders: all eight scrollable pages at 900×640.
- Horizontal scrollbar maximum: zero for every visible page scroll area.
- The corrected 900×640 Dashboard showed separate preview, status panel, and control row.
- Empty camera/model backends were used; no camera, model inference, hotkey, or OS input was active.

## Honest remaining checks

- Human keyboard traversal through native file dialogs and the full-screen calibration flow.
- Native Windows 125% and 150% scaling evidence.
- A visual/keyboard pass with Windows High Contrast actually enabled.
- Live-camera visual states and broad calibrated screen reach.
