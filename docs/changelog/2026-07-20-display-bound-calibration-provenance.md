# 2026-07-20 - Display-bound calibration provenance

## Summary

Upgraded accepted-calibration storage to schema 2 with canonical UTC creation time and exact
physical primary-display geometry. Startup recovery now clears fake diagnostics when the current
primary display no longer matches the geometry used by the stored calibration.

## Added

- Immutable calibration provenance containing second-precision UTC creation time and validated
  signed physical-screen bounds.
- Checksummed schema-2 provenance fields for primary-screen left, top, width, and height.
- Sanitized Calibration UI text showing age context and display bounds.
- An explicit incompatible lifecycle state and event-only display-mismatch log.
- Tests for UTC enforcement, provenance round-trip, legacy preservation, lifecycle mismatch, and
  `MainWindow` SAFE startup behavior on changed geometry.

## Changed

- Accepted fits are provisioned against current native geometry before their schema-2 envelope is
  saved, so storage and fake diagnostics share the same validated rectangle.
- A storage failure leaves that current accepted pipeline volatile instead of performing another
  native geometry read.

## Safety decisions

- Schema-1 envelopes lack display provenance, so they remain on disk but cannot recover; the user
  must recalibrate.
- Geometry comparison includes origin and dimensions, not only width and height.
- A mismatch immediately removes the briefly prepared startup pipeline before tracking begins.
- Stored creation time and display geometry are local provenance, not proof of calibration quality.
- Recovery remains structurally unable to restore consent, arm Live Input, or call an executor.

## Verification

Focused Ruff and strict mypy passed; 33 persistence, lifecycle, and composition-root tests passed in
6.40 seconds.

Full repository gate:

- Ruff format: 138 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 138 source files.
- Native Windows pytest: 700 passed in 20.17 seconds.

## Known limitations

- Display identity beyond its physical rectangle is not stored.
- Calibration age is shown but no evidence-backed expiry duration is imposed.
- Explicit replace/forget controls, scaling-matrix QA, and all gaze pointer output remain pending.

## Next task

Add an explicit, recoverable Forget saved calibration control that clears fake provisioning before
moving the envelope to a timestamped deleted backup, without changing Live Input state.
