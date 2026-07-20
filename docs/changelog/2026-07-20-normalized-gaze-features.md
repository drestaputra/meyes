# 2026-07-20 - Normalized gaze feature foundation

## Summary

Started Phase 5 with a dormant, fail-closed binocular gaze feature path. MEYES now projects each
iris center onto horizontal and vertical eye-local axes, combines the two eyes, and exposes the
uncalibrated feature in Diagnostics. This iteration does not map the feature to a screen or move
the operating-system pointer.

## Added

- Typed `GazeFeatureVector`, `GazeFeatureObservation`, and explicit feature-status models.
- Pixel-aspect-correct projection against MediaPipe eye corner and eyelid landmarks.
- Independent left/right features plus a binocular mean for the future calibration collector.
- Explicit states for missing face, missing openness, closed eyes, unavailable landmarks, invalid
  geometry, and invalid timestamps.
- Qt-owned feature publication, tracking-timeout expiry, suspension clearing, and lifecycle
  generation guards.
- Native Diagnostics status and eye-relative X/Y values with an explicit uncalibrated warning.

## Safety decisions

- No calibration mapper, cursor smoother, screen mapping, pointer timer, or input-executor call was
  added in this iteration.
- A feature is unavailable unless both eyes are open and both iris/eye geometries are complete.
- Invalid backend runtime types, non-finite values, degenerate axes, stale frames, and old lifecycle
  generations fail closed without repopulating gaze state.
- Raw eye-relative ratios are not clamped; the later calibration collector must reject outliers
  instead of silently converting them into plausible edge samples.
- Preview mirroring remains separate from canonical, unmirrored processing coordinates.

## Official references

- [MediaPipe Iris overview](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/iris.md)
- [MediaPipe Face Landmarker eye and iris topology](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/python/vision/face_landmarker.py)
- [MediaPipe Face Mesh coordinates](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/face_mesh.md)

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes\domain\observations.py src\meyes\vision\gaze_features.py src\meyes\vision\controller.py src\meyes\ui\diagnostics_page.py tests\unit\test_gaze_features.py tests\unit\test_vision_controller.py tests\unit\test_diagnostics_page.py
.\.venv\Scripts\python.exe -m mypy src\meyes\domain\observations.py src\meyes\vision\gaze_features.py src\meyes\vision\controller.py src\meyes\ui\diagnostics_page.py tests\unit\test_gaze_features.py tests\unit\test_vision_controller.py tests\unit\test_diagnostics_page.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_gaze_features.py tests\unit\test_vision_controller.py tests\unit\test_diagnostics_page.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 51 passed in 4.56 seconds.

Full repository gate:

- Ruff format: 105 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 105 source files.
- Pytest: 544 passed in 14.37 seconds.

## Native QA

- Native Windows Diagnostics render: passed at 1200 x 760 with gaze status, values, and warning
  visible and no horizontal overflow.
- The render used synthetic observations; camera, model backends, hotkey registration, and
  `SendInput` were not activated.

## Known limitations

- The values are landmark-derived features, not calibrated predictions or accuracy claims.
- Head-pose compensation, sample collection, outlier rejection, mapping, smoothing, and broad
  screen-reach validation remain pending.
- Ordinary-webcam lighting, reflections, eyelid occlusion, and pose can affect landmark quality.

## Next task

Build a guided nine-point calibration sample collector with bounded per-target samples and explicit
quality rejection, still without enabling pointer output.
