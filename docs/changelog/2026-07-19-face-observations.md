# 2026-07-19 — Face observations

## Summary

Implemented Phase 2A: a local MediaPipe Face Landmarker adapter, framework-independent face/eye observations, verified model asset, and latest-frame vision worker. The pipeline does not emit gestures or inject operating-system input yet.

## Added

- Official MediaPipe `face_landmarker.task` float16 model stored locally.
- Model source, size, SHA-256, and packaging-license follow-up documentation.
- Environment-overridable model path resolution.
- Normalized domain models for face landmarks and iris centers.
- Independent left/right eye-openness values derived from `eyeBlinkLeft` and `eyeBlinkRight` blendshapes.
- Honest optional confidence: landmark presence is used only when the model supplies it.
- MediaPipe VIDEO-mode adapter with monotonically increasing timestamps.
- Latest-frame vision worker with:
  - camera-frame dropping under inference load;
  - inference FPS and capture-to-observation latency;
  - explicit health and error state;
  - deterministic backend close and observation clearing.
- Webcam-free tests for result normalization and stale-frame skipping.
- Model integrity test using the recorded SHA-256.
- Raw, unmirrored camera frame buffer exposure for the vision pipeline.

## Changed

- Added MediaPipe as a runtime dependency.
- Consolidated OpenCV on MediaPipe's `opencv-contrib-python` dependency to avoid two packages owning the `cv2` namespace.
- Updated README, root changelog, and Phase 2 TODO progress.

## Verification

Automated commands:

```powershell
.\scripts\check.ps1
```

Expected iteration result:

- Ruff formatting and lint: passed.
- mypy strict: passed.
- pytest: 27 passed.

Physical local smoke:

```text
Model resolved from resources/models/face_landmarker.task
Camera devices detected: 1
MediaPipe task initialized with XNNPACK CPU delegate
Face observation returned without saving a frame
```

The smoke test did not require a face to be present; it verified camera-to-model execution and normalized empty-face behavior. No frames were saved or uploaded.

## Known limitations

- The face worker is not connected to the live dashboard yet.
- A user-facing face-detection/eye-openness diagnostic view is not yet present.
- Wink semantics, blink suppression, cooldown, and event fixtures remain for Phase 2B.
- Model redistribution requirements must be checked again during packaging.
- Physical smoke returned no face in the sampled frames, so live eye-openness values still require an on-camera manual test.

## Next task

Implement Phase 2B: deterministic left/right wink state machines with minimum/maximum duration, both-eye sync suppression, cooldown, stale-observation reset, semantic gesture events, and recorded JSON fixture tests.
