# 2026-07-19 — Temple tap and hold semantics

## Summary

Completed Phase 3 by converting stabilized per-side temple proximity into semantic tap,
hold-start, and hold-end events. The classifier is framework-independent and remains inside
Safe Mode: no event is bound to scrolling, mouse, keyboard, or another operating-system input.

## Added

- Persisted `temple_hold_threshold_ms` with the specified `550 ms` default.
- Persisted `temple_cooldown_ms` with the specified `250 ms` default.
- Independent left/right interaction state machines with Waiting-for-Far, Idle, Pressed,
  Holding, and Cooldown states.
- A mandatory stable Far baseline after startup, reset, or tracking loss, preventing an
  already-near hand from triggering when tracking begins.
- Tap emission only after a confirmed stable Far release before the hold threshold.
- One hold-start after fresh Near evidence reaches the threshold and one corresponding
  hold-end after release, timeout, pause, stop, or reset.
- Deterministic left-before-right ordering for simultaneous semantic events.
- Recorded right-tap and left-hold state fixtures under
  `tests/fixtures/observation_sequences/`.
- Controller integration tests for tap release, hold release, watchdog expiry, and idempotent
  lifecycle flushing.

## Timing and ordering boundary

- Stable proximity capture timestamps, not processing latency, measure tap and hold duration.
- Hold-start requires a fresh ordered Near capture at or beyond the deadline. Watchdog time can
  cancel a pending press or end a hold, but cannot promote one without new evidence.
- Fresh evidence uses strict sequence, capture-time, arrival-time, and post-expiry watermarks.
  Evidence captured at or before an expiry cannot travel backward into a new interaction.
- Raw Far-candidate onset is retained through exit stabilization. A physical release that began
  before the hold threshold remains a tap even if stable Far confirmation arrives afterward.
- A confirmed Far release exactly at the hold boundary emits hold-start followed by hold-end;
  it never emits a tap.
- Unknown before hold-start cancels the candidate without creating a tap or inferred hold.
- Cooldown never queues a Near state. A side must be observed Far after the deadline before a
  later Near state can start another interaction.

## Lifecycle and safety invariants

- Every emitted hold-start has exactly one eventual hold-end.
- No hold-end is emitted without a prior hold-start.
- One interaction emits either a tap or a hold-start/hold-end pair, never both.
- Timeout and repeated reset paths are idempotent.
- Gesture computation stays under the existing controller lock; Qt signals and logging occur
  after the lock is released.
- Proximity transitions remain separate from semantic events in Diagnostics.
- Binding, action execution, mouse, keyboard, and scroll code remain disconnected.

## Verification

```powershell
.\scripts\check.ps1
```

- Ruff format: 62 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 62 source files.
- Pytest: 175 passed in 8.20 seconds.
- Focused temple/config/controller/Diagnostics suite: 99 passed in 5.64 seconds.
- Native Qt visual QA: Diagnostics rendered at 1200 x 760 with the Safe Mode boundary,
  proximity state, and `LEFT HOLD END`, `LEFT HOLD START`, and `RIGHT TAP` rows visible
  without clipping.

## Known limitations

- Hold duration begins when Near becomes stable, after proximity stabilization, rather than
  at the first raw threshold crossing.
- The watchdog uses a bounded timer cadence, so hold-end follows the first watchdog tick after
  the strict tracking timeout instead of claiming a hard real-time deadline.
- Hold threshold and cooldown are validated configuration values but do not yet have a
  user-facing sensitivity control.
- Live physical tap/hold quality remains dependent on camera view, landmark confidence,
  lighting, and occlusion; deterministic state semantics do not claim universal live accuracy.
- Semantic events are visible in Diagnostics but cannot yet trigger a user binding or OS action.

## Next task

Begin Phase 4 with validated action and binding models plus a fake executor. Keep the Windows
input backend disconnected until action validation, continuous-action release, exception, and
emergency-pause tests are complete.
