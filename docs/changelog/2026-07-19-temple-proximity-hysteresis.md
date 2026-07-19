# 2026-07-19 — Temple proximity hysteresis

## Summary

Converted raw same-side fingertip-to-temple ratios into stable, independently timed
Near/Far/Unknown states. The state machine is framework-independent and remains inside the
Safe Mode diagnostics boundary: it emits no tap, hold, mouse, keyboard, or scroll action.

## Added

- Persisted temple enter ratio `0.075`, exit ratio `0.095`, and stabilization time `180 ms`.
- Validation that the enter threshold is strictly lower than the exit threshold.
- Immutable left/right proximity snapshots and independent side trackers.
- Inclusive enter/exit thresholds, stabilization on both entry and release, and dead-band
  cancellation for jitter resistance.
- Immediate initial Far evidence, while Near always requires a later stabilized sample.
- Valid missing-hand evidence as Far and explicit `EXPIRED` input as Unknown.
- Strict sequence and capture-time ordering guards plus processed-time sanity validation.
- Capture-time stabilization and freshness evidence, so delayed processing cannot create
  false dwell time or extend state lifetime.
- Malformed, duplicate-side, negative, non-finite, and unknown-side ratio rejection.
- Independent watchdog expiry after the configured `250 ms` tracking timeout, including when
  the raw feature tracker's latest observation is invalid.
- Qt signals for transition-only proximity snapshots and lifecycle clearing.
- Left and right Near/Far/Unknown labels alongside the unchanged raw ratios in Diagnostics.

## Changed

- All non-out-of-order raw temple features now pass through one serialized controller method
  before reaching derived state and UI signals.
- A stale face observation resets wink state only; temple state retains its own freshness and
  expires through its independent watchdog path.
- Suspend and stop reset both raw feature history and derived proximity state, then emit
  separate clear signals.
- README, judge instructions, Build Week scope, root changelog, and Phase 3 checklist now
  describe the implemented state boundary.

## Safety invariants

- Only `READY` and `NO_ELIGIBLE_HANDS` are valid state evidence.
- Invalid observations retain stable state only until timeout and cancel any in-progress
  transition candidate.
- A cached Near/Far state cannot survive tracking loss beyond the timeout merely because the
  latest raw feature status is invalid.
- Duplicate or regressing valid samples cannot complete a transition.
- Processing latency cannot substitute for physical capture-time dwell.
- Proximity snapshots do not enter the semantic event log and cannot reach an action layer.
- Operating-system input remains disconnected.

## Verification

```powershell
.\scripts\check.ps1
```

Measured results:

- Ruff formatting: passed, 60 files checked.
- Ruff lint: passed.
- mypy strict: passed, 60 source files checked.
- pytest: 133 passed in 7.19 seconds.
- Detector, config, controller, and Diagnostics focused verification: 57 passed.
- Native Windows visual render: passed at 1200 × 760; both state labels, raw ratios, and the
  empty semantic-event panel were readable and unclipped.
- Git diff whitespace check: passed.

## Known limitations

- Thresholds and stabilization are validated configuration values but do not yet have a
  user-facing sensitivity control.
- Confidence and palm-plausibility gating do not extend beyond the upstream feature
  eligibility checks.
- Near/Far transitions do not yet classify tap, hold-start, or hold-end events.
- No proximity state is connected to mouse, keyboard, scroll, or another OS action.
- Live physical Near/Far transition quality was not claimed in this iteration; deterministic
  normalized sequences cover its state semantics.

## Next task

Build a framework-independent temple tap/hold classifier on top of stabilized proximity
states. Emit semantic tap, hold-start, and hold-end events only, end held state on Unknown,
and keep bindings and operating-system input disconnected.
