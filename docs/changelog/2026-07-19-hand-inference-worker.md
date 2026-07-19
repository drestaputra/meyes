# 2026-07-19 — Hand inference worker

## Summary

Implemented the lower-cadence Phase 3 hand worker using the shared latest-frame camera buffer. Hand inference is bounded by a monotonic wall clock, runs independently from face inference, and cannot publish an in-flight result after tracking is suspended or stopped.

## Added

- Thread-safe latest-hand-observation buffer.
- Dedicated hand inference worker with a default 10 FPS resource budget.
- Independent hand health snapshots for status, inference FPS, hand count, latency, and errors.
- Worker-thread construction and deterministic closure of the MediaPipe backend.
- Shared lifecycle result gate for generation-based publication control.
- Explicit resume behavior after a suspended camera pipeline.
- Tests for cadence, newest-frame selection, queued-frame dropping, invalid rate values, in-flight invalidation, resume, stop, and single backend closure.

## Changed

- Hand cadence now uses `time.monotonic()` rather than camera capture timestamps.
- Face inference uses the same result gate, closing an existing suspend/stop race.
- Vision controller suspension invalidates worker publications before resetting gesture state.
- A timed-out face worker reference is retained so shutdown can be retried.
- Updated README, root changelog, and Phase 3 TODO progress.

## Safety invariants

- Capture timestamps cannot cause hand inference to exceed its wall-clock budget.
- The worker always selects the newest pending frame when its next inference slot is due.
- Camera timestamp jumps or regressions cannot starve or accelerate the scheduler.
- A result started before suspend or stop cannot refill the buffer or emit a callback afterward.
- Resume begins a fresh result generation and accepts only newer camera frames.
- Face and hand adapters remain read-only consumers of the shared frame array.

## Verification

```powershell
.\scripts\check.ps1
```

Results:

- Ruff formatting: passed, 56 files checked.
- Ruff lint: passed.
- mypy strict: passed, 56 source files checked.
- pytest: 56 passed.
- Worker race/cadence stress: 13 focused tests passed in five consecutive runs.

Critical assertions:

- Large forward and backward capture-timestamp jumps do not bypass the wall-clock cadence.
- Frames queued during a slow inference collapse to the newest sequence.
- Zero, negative, `NaN`, and infinite target rates are rejected.
- In-flight results are discarded across invalidation and stop.
- Resume publishes a new result without restarting the native backend.
- Each native backend closes exactly once.

## Known limitations

- The hand worker is not yet composed into the live Qt vision controller.
- Hand observations are not yet paired with face observations.
- Actual negotiated frame dimensions are not yet carried into observations for aspect-correct temple geometry.
- Temple proximity, hysteresis, and tap/hold semantics are not yet implemented.
- Bindings and Windows input remain intentionally disconnected.

## Next task

Implement aspect-correct temple features: include actual frame dimensions in face and hand observations, pair fresh observations by capture time, calculate anatomical temple anchors and face-width-normalized index-fingertip distance, and reject stale or wrong-hand candidates deterministically.
