# 2026-07-20 - Cursor freeze and resume gate

## Summary

Added a dormant, fail-closed permission gate for future gaze movement. It starts suspended, tracks
overlapping temple holds, treats taps as short freeze pulses, and resumes only after a configurable
stabilization delay. It has no pointer-output consumer.

## Added

- Suspended, open, temple-frozen, and resume-delay states with immutable snapshots.
- Independent left/right active-hold ownership and same-frame start/end support.
- Tracking suspend/resume and reset semantics that clear stale holds.
- Monotonic timestamp/source-sequence validation and adjacent duplicate idempotence.
- Cursor configuration for temple freeze and the default 120 ms resume delay.
- Tests for overlap, taps, delay boundaries, tracking loss, disabled gesture policy, ordering, and reset.

## Safety decisions

- Tracking unavailable always blocks movement, even when temple freezing is configured off.
- Lifecycle reset returns to suspended; it never implicitly opens the gate.
- Event ordering is validated atomically before state mutation.
- No runtime controller, timer, mapper, or executor consumes the gate.

## Verification

Focused Ruff, strict mypy, and pytest passed; 21 focused tests passed in 1.05 seconds.

Full repository gate:

- Ruff format: 126 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 126 source files.
- Native Windows pytest: 649 passed in 18.54 seconds.

## Known limitations

- The semantic stream exposes hold start/end and release-time taps, not raw press onset.
- Runtime composition, native screen acquisition, persistence, and pointer output remain pending.

## Next task

Compose a fake-only cursor pipeline from accepted calibration, smoothing, mapping, and the movement
gate, with lifecycle and freshness tests and no `SendInput` connection.
