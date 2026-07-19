# MEYES Todo List

Last updated: 2026-07-19  
Source of truth: [`../DEVELOPMENT_PLAN.md`](../DEVELOPMENT_PLAN.md)

## Working rules

- Complete tasks in phase order unless a documented blocker requires a change.
- Keep camera processing local and never store frames by default.
- Do not connect vision detection directly to Windows input execution.
- Update this file and add a dated changelog entry after every implementation batch.
- Run tests and static checks before marking an implementation task complete.
- Record limitations and follow-up work instead of hiding partial behavior.

## Current milestone — Phase 0 + Phase 1

### Repository foundation

- [x] Create `pyproject.toml` for Python 3.11 and the required dependencies.
- [x] Create the `src/meyes` package and application entry point.
- [x] Add the PySide6 application shell.
- [x] Add typed application and camera state models.
- [x] Add Pydantic configuration models and safe Windows data paths.
- [x] Add corrupt-configuration backup and recovery.
- [x] Add rotating structured logs.
- [x] Configure Ruff.
- [x] Configure Pyright or mypy.
- [x] Configure pytest.
- [x] Add PowerShell scripts for run, test, and static checks.
- [x] Add `README.md` and root `CHANGELOG.md` release summary.

### Camera vertical slice

- [x] Define a camera interface independent of OpenCV.
- [x] Enumerate available cameras.
- [x] Implement the OpenCV capture worker.
- [x] Implement latest-frame-only buffering.
- [x] Keep preview mirroring separate from processing coordinates.
- [x] Add the camera selector.
- [x] Add a responsive camera preview.
- [x] Add start, pause, resume, and stop controls.
- [x] Display measured capture and preview FPS.
- [x] Display explicit camera health states.
- [x] Recover from camera open/read failure without crashing.
- [x] Stop workers deterministically before releasing camera resources.

### Phase 0 + Phase 1 verification

- [x] Add configuration round-trip tests.
- [x] Add corrupt-configuration recovery tests.
- [x] Add camera-state transition tests without requiring a webcam.
- [x] Verify the UI stays responsive during capture.
- [x] Verify switching or reconnecting a camera does not leak resources.
- [x] Verify pause and shutdown are deterministic.
- [x] Run unit tests.
- [x] Run Ruff lint and format checks.
- [x] Run the selected type checker.
- [x] Update the root changelog and add a dated entry under `docs/changelog/`.
- [x] Document commands, results, changed files, and known limitations.

## Completed — Phase 2

- [x] Integrate MediaPipe Face Landmarker behind an adapter.
- [x] Emit normalized face and eye observations.
- [x] Implement independent eye-openness measurements.
- [x] Implement left/right wink state machines.
- [x] Suppress natural both-eye blink events.
- [x] Add cooldown and stale-observation handling.
- [x] Add recorded observation fixtures and regression tests.
- [x] Show wink events in diagnostics with OS input disabled.

## Backlog — Phase 3

- [x] Integrate MediaPipe Hand Landmarker behind an adapter.
- [x] Canonicalize handedness and mirror conversion in one place.
- [x] Run hand inference at a lower independent cadence.
- [x] Calculate face-width-normalized temple distance.
- [x] Compose face and hand workers into Qt-safe live diagnostics.
- [x] Expire live temple features after the configured tracking timeout.
- [ ] Implement temple proximity hysteresis.
- [ ] Implement tap, hold-start, and hold-end states.
- [ ] End continuous states after tracking timeout.
- [ ] Test wrong-hand, unstable-candidate, release, and tracking-loss sequences.

## Backlog — Phase 4

- [ ] Create validated action and binding models.
- [ ] Create default and user profile repositories.
- [ ] Implement the Windows `SendInput` executor.
- [ ] Implement mouse click and scroll actions.
- [ ] Implement continuous scroll with fail-safe release.
- [ ] Implement validated keyboard shortcuts.
- [ ] Implement the global emergency pause shortcut.
- [ ] Implement no-input safe mode.
- [ ] Test all actions through a fake executor.

## Backlog — Phase 5

- [ ] Extract normalized gaze features.
- [ ] Build the guided nine-point calibration flow.
- [ ] Reject calibration outliers.
- [ ] Implement a replaceable calibration mapper.
- [ ] Implement adaptive cursor smoothing.
- [ ] Map gaze to the primary Windows screen.
- [ ] Freeze and safely resume cursor movement around temple gestures.
- [ ] Validate broad screen reach after calibration.

## Backlog — Phase 6

- [ ] Complete the first-run setup wizard.
- [ ] Complete Dashboard, Calibration, Bindings, Sensitivity, Camera, Profiles, Diagnostics, and Privacy views.
- [ ] Add system tray controls.
- [ ] Add profile import/export and restore defaults.
- [ ] Verify keyboard-only operation and visible focus.
- [ ] Verify Windows 100%, 125%, and 150% scaling.
- [ ] Verify Windows high-contrast behavior.
- [ ] Review screens against [`../DESIGN.md`](../DESIGN.md).

## Backlog — Phase 7

- [ ] Select Nuitka or `pyside6-deploy` using measured build results.
- [ ] Bundle models, icons, and default resources.
- [ ] Add startup and packaging error recovery.
- [ ] Document application signing requirements.
- [ ] Run a clean-machine smoke test.
- [ ] Complete privacy and troubleshooting documentation.
- [ ] Profile performance and optimize only measured bottlenecks.
- [ ] Complete the MVP acceptance checklist.

## Deferred after MVP

- [ ] Multi-monitor calibration.
- [ ] Advanced ONNX gaze estimation.
- [ ] Per-application profiles and automatic switching.
- [ ] Drag-and-drop, dwell-click, and additional gestures.
- [ ] macOS and Linux input backends.
- [ ] Optional native optimization for measured hot paths.
