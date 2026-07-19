# 2026-07-19 — Safe Mode diagnostics

## Summary

Completed Phase 2C by connecting the camera frame buffer to MediaPipe face inference and the semantic wink engine through a Qt-safe controller. Added a live Diagnostics page that exposes observations and events while keeping all operating-system input disconnected.

## Added

- Qt vision controller with observation, health, and semantic event signals.
- Camera-aware start, suspend, resume, and shutdown coordination in the main window.
- Live face detection, frame sequence, inference FPS, and processing latency indicators.
- Independent left and right eye-openness meters.
- Recent semantic wink event log with source duration and a clear action.
- Permanent Safe Mode banner confirming that no mouse or keyboard input is sent.
- Placeholder pages for unfinished navigation destinations so the application structure remains stable.
- Controller and widget tests for event publication, state invalidation, and diagnostics rendering.

## Changed

- Face inference backends are now constructed inside the vision worker thread, keeping native model initialization outside the Qt UI thread.
- The main window now hosts a stacked page layout and connects camera health to the vision lifecycle.
- Navigation and diagnostics styling now use scoped object selectors to avoid leaking styles into unrelated controls.
- Updated README, root changelog, and Phase 2 TODO progress.

## Verification

```powershell
.\scripts\check.ps1
```

Results:

- Ruff formatting: passed, 51 files checked.
- Ruff lint: passed.
- mypy strict: passed, 51 source files checked.
- pytest: 40 passed.
- Native Windows visual render: passed at 1200 × 760.
- Physical webcam-to-MediaPipe smoke test: 12 observations processed; camera and vision workers stopped cleanly.

Critical assertions:

- Camera frames reach the MediaPipe adapter without blocking the UI thread.
- Semantic wink events appear in Diagnostics and have no OS-input consumer.
- Suspending tracking clears stale face and gesture state.
- Worker-owned MediaPipe resources close during deterministic shutdown.

## Known limitations

- The physical smoke sample contained no detected face, so live on-camera wink tuning still needs a user-present validation session.
- Gesture thresholds are configuration-backed but do not yet have UI controls.
- Hand and temple gesture detection has not been implemented.
- Bindings and Windows input remain intentionally disconnected.

## Next task

Start Phase 3A: integrate MediaPipe Hand Landmarker behind an adapter, normalize handedness and mirror conversion in one place, and add deterministic observation tests before implementing temple gesture semantics.
