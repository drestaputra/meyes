# 2026-07-21 - Sensitivity view

## Summary

Replaced the Sensitivity placeholder with a native editor for the existing validated cursor
smoothing and movement-gate configuration.

## Safety and lifecycle

- Changes remain an isolated draft until Save sensitivity is selected.
- Saving first releases Live Input; release failure keeps the prior runtime/configuration and the
  dirty draft.
- Persistence failure keeps the prior runtime settings.
- A successful save updates future pipeline settings and rebuilds a pipeline only when its accepted
  calibration is still active.
- Display mismatch/native invalidation removes the volatile calibration proof, so a later settings
  change cannot resurrect the invalid pipeline.
- Missing calibration updates settings for the future without reading screen geometry or creating
  OS input.

## Interface

- Minimum cutoff, speed response, derivative cutoff, and stale-reset gap controls.
- Optional temple-gesture freeze and bounded resume delay.
- Explicit dirty/clean feedback, default staging, and save result messaging.
- Scrollable 900x640 layout using the locked canvas/surface/focus tokens.

## Verification

- Twelve provisioner tests cover no-calibration, accepted rebuild, exact active-geometry parity, and
  no resurrection after mismatch.
- Four page tests cover initial values, complete save, failed-save draft retention, and default
  staging.
- MainWindow integration covers release request, atomic config persistence, runtime settings, and
  retained Safe state.
- Native 900x640 visual QA confirmed the scrollable token-based layout without horizontal overflow.
- Ruff formatting/lint and strict mypy passed across 146 source files; all 756 tests passed on native
  Windows Qt.
