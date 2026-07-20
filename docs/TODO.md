# MEYES Todo List

Last updated: 2026-07-20
Source of truth: [`../DEVELOPMENT_PLAN.md`](../DEVELOPMENT_PLAN.md)

## Working rules

- Complete tasks in phase order unless a documented blocker requires a change.
- Keep camera processing local and never store frames by default.
- Do not connect vision detection directly to Windows input execution.
- Update this file and add a dated changelog entry after every implementation batch.
- Run tests and static checks before marking an implementation task complete.
- Record limitations and follow-up work instead of hiding partial behavior.

## OpenAI Build Week submission gate — due 2026-07-21 17:00 PT

- [x] Confirm an authenticated Devpost registration and pre-draft project record exist.
- [x] Align README and package metadata with the actual Safe Mode scope.
- [x] Record explicit GPT-5.6 evidence beginning at commit `57e08f2`.
- [x] Add source setup, judge quickstart, privacy disclosure, MIT license, Apache-2.0 text,
  model provenance, and primary third-party notices.
- [x] Preserve dated, unsquashed build-period commit history.
- [ ] Human entrant confirms age, residence/domicile, sanctions, conflicts, originality,
  ownership, third-party rights, and team-representative eligibility under the Official Rules.
- [ ] Human entrant confirms **Apps for Your Life** as the final category.
- [ ] Complete the required submitter-type and country fields with actual entrant information.
- [ ] Human owner confirms `drestaputra` is the correct MIT copyright holder.
- [ ] Rename and complete Devpost project `1342722` in the entrant's own voice.
- [ ] Add a human-approved tagline, description, Built With list, repository URL, and video
  URL to the Devpost project; add the judge quickstart to the optional testing field.
- [ ] Record the `/feedback` Session ID from the task where most core functionality was built.
- [ ] Verify the judge quickstart on a clean Windows 10/11 x64 environment.
- [ ] Make the repository public with its license, or invite `testing@devpost.com` and
  `build-week-event@openai.com` and verify both can access it.
- [ ] Add every teammate to Devpost and have them accept before the deadline, if applicable.
- [ ] Record and publish a clear YouTube demo shorter than 3:00 with audio covering what was
  built and how Codex and GPT-5.6 were used.
- [ ] Review the demo for consent, private information, trademarks, and copyrighted media.
- [ ] Human-edit the Devpost description in English and map demonstrated evidence to all four
  judging criteria without claiming roadmap features.
- [ ] Recheck the Official Rules, Updates, required fields, video visibility, and repository
  access immediately before submission.
- [ ] Keep the repository, video, and testing path free and accessible through the official
  judging end (currently 2026-08-05 17:00 PT under the Rules; recheck before submitting).
- [ ] Confirm the final Devpost state is **Submitted**, not Draft, before the deadline.

## Completed — Phase 0 + Phase 1

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

## Completed — Phase 3

- [x] Integrate MediaPipe Hand Landmarker behind an adapter.
- [x] Canonicalize handedness and mirror conversion in one place.
- [x] Run hand inference at a lower independent cadence.
- [x] Calculate face-width-normalized temple distance.
- [x] Compose face and hand workers into Qt-safe live diagnostics.
- [x] Expire live temple features after the configured tracking timeout.
- [x] Implement temple proximity hysteresis.
- [x] Implement tap, hold-start, and hold-end states.
- [x] End continuous states after tracking timeout.
- [x] Test wrong-hand, unstable-candidate, release, and tracking-loss sequences.

## Backlog — Phase 4

- [x] Create validated action and binding models.
- [x] Create default and user profile repositories.
- [x] Implement the Windows `SendInput` executor with partial-send and release tests.
- [x] Implement mouse click and scroll action dispatch through the fake executor.
- [x] Implement poll-driven continuous scroll with fail-safe release and no catch-up.
- [x] Implement validated keyboard shortcut dispatch through the fake executor.
- [x] Implement the global emergency pause shortcut.
- [x] Add the dormant Windows global-hotkey registration, native-event filter, and physical-input
  preflight foundation without registering it in the Safe Mode application.
- [x] Add a dormant per-session live controller with exact typed consent, hotkey-first physical
  preflight, release-first arming, emergency release, and fail-closed recovery tests.
- [x] Add explicit live-mode consent, physical-key preflight, emergency pause, and a release-first
  arm/disarm UI that constructs the native executor only after the user opts in.
- [x] Wire semantic events to real `SendInput` only while armed and disarm on camera lifecycle,
  profile transition, fault, page destruction, and application close.
- [x] Implement dispatcher no-input safe mode with an explicit arm gate.
- [x] Wire live semantic events to a Qt-owned fake-only simulation and Diagnostics trace.
- [x] Add a durable user-facing profile catalog and all-disabled profile creation.
- [x] Activate selected profiles through a release-first paused transition with config rollback.
- [x] Preview the active profile's six simulated gesture bindings.
- [x] Test all actions through a fake executor.
- [x] Add a safe draft-based binding editor without enabling operating-system input.
- [x] Add inactive profile rename, exact-confirmation recoverable deletion, and restore-default
  workflows with built-in and active-profile protections.
- [ ] Add profile import/export workflows.

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
- [ ] Add profile import/export.
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
