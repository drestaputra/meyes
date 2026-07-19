# 2026-07-19 — Live hand and temple diagnostics

## Summary

Composed the local face and lower-cadence hand pipelines in one Qt controller, serialized their callbacks on the UI thread, and exposed live hand and temple features in Diagnostics. The iteration remains locked in Safe Mode: semantic observations are visible, but no mouse or keyboard action consumer exists.

## Added

- Hand worker construction, start, resume, suspend, and stop alongside the face worker.
- Qt-main-thread serialization for face and hand observations and health.
- Latest-only callback coalescing for both results and per-frame health updates.
- Delivery-generation and worker-instance envelopes that reject callbacks from suspended lifecycles or replaced workers.
- Capture-time freshness validation before a face observation can reach the wink engine or public UI signal.
- A `QTimer` watchdog whose cadence and expiry derive from `GestureSettings.tracking_timeout_ms`.
- Public hand observation, hand health, temple feature, and corresponding clear signals.
- Three-panel Diagnostics view for face observations, hand and temple features, and semantic events.
- Live hand count, inference FPS, latency, feature status, and left/right temple-distance ratios.
- Controller tests for callback backlog, stale delivery, delayed face/hand ordering, automatic expiry, and partial shutdown failure.

## Changed

- The production composition root now supplies `MediaPipeHandLandmarker` to `MainWindow` and `VisionController`.
- Cached hand observations are re-paired when the relevant face result completes later.
- A fresh face arriving after the cached hand timeout emits an explicit `HAND_STALE` feature rather than reviving old hand input.
- Suspend and stop clear face, hand, temple tracker, pending callbacks, watchdog, and wink state together.
- Shutdown attempts both workers even if the first worker reports a timeout.
- README, root changelog, and Phase 3 TODO progress now describe live composition.

## Safety invariants

- All public UI-facing observation and health signals are emitted on the controller thread.
- A stalled UI cannot replay a wink sample after the configured tracking timeout.
- Only the latest queued face result, hand result, face health, and hand health is retained.
- Payloads from a suspended generation or replaced worker instance are ignored.
- Face/hand completion order cannot permanently hide a valid same-frame pair.
- Expiry is published once without waiting for another camera frame.
- No temple feature or semantic event is connected to an operating-system action.

## Verification

```powershell
.\scripts\check.ps1
```

Measured results:

- Ruff formatting: passed, 58 files checked.
- Ruff lint: passed.
- mypy strict: passed, 58 source files checked.
- pytest: 93 passed.
- Focused controller and temple tracker suites: 38 passed.
- Native Windows visual render: passed at 1200 × 760 with all three Diagnostics panels readable and unclipped.
- Physical camera-to-both-model smoke: passed for 10 seconds with 170 face observations, 52 hand observations, deterministic `stopped` status for all three workers, and no remaining `meyes-*` threads.
- No camera frames were saved. The physical sample contained no visible face or hand, so detection was not claimed.

Critical assertions:

- Callback backlog publishes only the newest result and health state for each worker.
- An old queued wakeup cannot lose the current-generation result after suspend/resume.
- A stale queued wink sample clears its candidate and cannot emit an event.
- Queued running health cannot repopulate Diagnostics after suspension; current terminal health remains visible.
- Hand-first/face-later completion becomes `READY` when fresh and `HAND_STALE` when the hand has expired.
- The watchdog emits one expiry transition and stops with the controller.
- Hand shutdown is still attempted when face shutdown times out.

## Known limitations

- Raw distance ratios are displayed but are not interpreted as proximity states yet.
- Hysteresis, stabilization, confidence/palm plausibility gates, tap, and hold are deferred.
- Hand inference cadence remains an internal default rather than a user-facing setting.
- The physical smoke environment did not contain a visible face or hand.
- Bindings and Windows input remain disconnected.

## Next task

Implement a framework-independent per-side temple proximity state machine with configurable enter/exit distance ratios and stabilization timing, consume only fresh valid features, fail closed on unavailable or timed-out input, and add deterministic boundary, jitter, wrong-side, and tracking-loss tests before tap/hold classification.
