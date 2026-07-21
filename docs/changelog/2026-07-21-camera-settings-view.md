# 2026-07-21 - Camera settings view

## Summary

Replaced the dedicated Camera navigation placeholder with a truthful capture-health and requested
capture-settings view. Dashboard remains the single place for camera selection, preview, and
start/pause/resume lifecycle controls.

## Safety and lifecycle

- Width, height, target FPS, and preview-only mirroring remain a complete validated draft.
- Saving is enabled only while the camera controller reports Stopped.
- Save releases Live Input before persistence and controller mutation.
- Persistence failure retains prior runtime settings and the dirty draft.
- Applying complete controller settings is rejected while capture is active.
- Dashboard mirrors the same settings signal, so requested resolution and preview mirroring remain
  synchronized across views.
- The Camera view never starts capture, constructs vision models, or arms native output.

## Interface

- Current capture state, measured FPS, consecutive failures, and latest health/error message.
- Bounded requested width, height, target FPS, and preview-only mirror controls.
- Dirty/clean state, default staging, stopped-only save, and a visible stop action while active.
- Scrollable 900x640 token-based layout without horizontal overflow.

## Verification

- Six controller tests cover complete stopped updates, active-capture rejection, capture lifecycle,
  and synchronized settings signals.
- Four page tests cover safe initial state, complete saves, active-capture blocking, health, and
  external settings synchronization.
- MainWindow integration covers release request, persistence, controller update, and Safe state.
- Native 900x640 visual QA confirmed the scrollable token-based layout without horizontal overflow.
- Ruff formatting/lint and strict mypy passed across 148 source files; all 763 tests passed on native
  Windows Qt.
