# 2026-07-19 — Wink state machine

## Summary

Implemented Phase 2B: deterministic independent wink semantics with both-eye blink suppression, hysteresis, duration limits, cooldown, tracking timeout, configuration validation, and recorded observation fixtures. The gesture engine emits semantic events only; no binding or operating-system input path is connected.

## Added

- Gesture event vocabulary and immutable timestamped event model.
- Central gesture engine for routing face observations through state machines.
- Independent left/right eye state classification with open/closed hysteresis.
- Wink candidate lifecycle with:
  - minimum stable duration;
  - maximum accepted duration;
  - at-most-once emission per sustained closure;
  - global cooldown;
  - no queued event when closure begins during cooldown.
- Both-eye blink suppression using synchronized closure timing and current dual-closed state.
- Immediate candidate cancellation on face/eye data loss.
- Tracking-gap and non-monotonic observation rejection.
- Persisted Pydantic gesture settings in milliseconds with threshold/duration order validation.
- Millisecond-to-second composition mapping for the runtime detector.
- Recorded JSON fixtures for left wink, right wink, and natural both-eye blink.
- Regression tests for both-eye suppression, one-shot emission, cooldown, tracking loss, stale timing, max duration, and config mapping.

## Changed

- Added the `gestures` section to version 1 configuration with safe defaults.
- Updated README, root changelog, and Phase 2 TODO progress.

## Verification

```powershell
.\scripts\check.ps1
```

Results:

- Ruff formatting: passed, 46 files checked.
- Ruff lint: passed.
- mypy strict: passed, 46 source files checked.
- pytest: 37 passed.

Critical assertions:

- Natural both-eye blink emits no wink event.
- Sustained left wink emits exactly one `LEFT_WINK`.
- Right wink emits exactly one `RIGHT_WINK`.
- A wink begun during cooldown is not emitted later.
- Face loss and long observation gaps cancel an in-progress candidate.
- Closures beyond maximum duration do not become winks.

## Known limitations

- Events are not yet visible in the application UI.
- Live thresholds cannot yet be adjusted without editing local configuration.
- Physical on-camera wink testing remains pending until the diagnostics controller is connected.
- Gesture bindings and Windows input remain intentionally disconnected.

## Next task

Implement Phase 2C: connect camera frames to the face worker and gesture engine, display face/eye/inference/event diagnostics in safe mode, manage start/pause/stop lifecycle across all workers, and perform live local wink validation without OS input.
