# 2026-07-20 - Qt fake cursor diagnostics

## Summary

Added a Qt-owned controller and Diagnostics fields for fake-only cursor candidates. Production is
wired to gaze, gesture, freshness, camera lifecycle, and shutdown signals but remains truthfully
unavailable because no accepted calibration plus native physical-screen pipeline is configured.

## Added

- Unavailable, suspended, blocked, ready, stale, and faulted diagnostic states.
- Separate capture time for smoothing and delivery monotonic time for gate/lifecycle ordering.
- Freshness watchdog expiry and late-clear-safe suspension semantics.
- Candidate normalized coordinates, physical pixels, gate state, and clamp evidence in Diagnostics.
- Injected-pipeline tests for ready, expiry, temple freeze/resume, numeric fault containment, and UI.

## Safety decisions

- The controller accepts no executor and stores only the latest candidate snapshot.
- Block, expiry, suspension, and fault clear all candidate fields.
- Production does not fabricate physical geometry or bypass the review-required calibration default.
- A gaze-clear signal arriving after camera suspension cannot overwrite the stronger suspended state.

## Verification

Focused Ruff and strict mypy passed; 24 focused tests passed in 4.95 seconds.

Full repository gate:

- Ruff format: 130 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 130 source files.
- Native Windows pytest: 661 passed in 19.80 seconds.

## Visual QA

- Native Diagnostics rendered at 1200 x 760 with the new cursor rows readable and scrollable.
- Production state displayed `Unavailable`; normalized/pixel/clamp fields displayed em dashes.

## Known limitations

- Native physical-screen acquisition, accepted calibration persistence, and production construction
  remain pending. No cursor timer or OS output exists.

## Next task

Implement a read-only DPI-aware native primary-screen geometry provider with fake Win32 boundary
tests, without enabling pointer movement.
