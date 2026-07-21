# 2026-07-21 - Privacy view

## Summary

Replaced the Privacy navigation placeholder with a native, read-only view of the product's current
data, storage, network, and real-input boundaries.

## Behavior

- Shows current Safe, Armed, Faulted, or Closed Live Input state without offering an arming control.
- States that raw frames, landmarks, gaze features, and calibration samples are not intentionally
  saved or uploaded.
- Distinguishes the missing MEYES/OpenAI upload path from MediaPipe's documented dependency network
  boundary.
- Lists selectable configuration, profile, accepted-calibration, and rotating-log paths.
- Provides guarded deletion guidance without deleting or creating any local file.

## Verification

- Three focused page tests cover all boundary copy, the four exact local paths, read-only
  construction, keyboard-selectable paths, and Live Input state updates.
- Eighteen Privacy/MainWindow integration tests passed.
- Native 900x640 visual QA confirmed canvas tokens, readable panels, vertical scrolling, and no
  horizontal scrollbar after one viewport correction.
- Ruff formatting/lint and strict mypy passed across 144 source files; all 748 tests passed on native
  Windows Qt.
