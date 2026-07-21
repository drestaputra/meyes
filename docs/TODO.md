# MEYES Todo List

Last updated: 2026-07-21
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
- [x] Verify a fresh Git clone with isolated locked dependencies, entry-point import, and full gate
  on the same Windows 11 host; retain the second-machine/live check as pending.
- [ ] Make the repository public with its license, or invite `testing@devpost.com` and
  `build-week-event@openai.com` and verify both can access it.
- [ ] Add every teammate to Devpost and have them accept before the deadline, if applicable.
- [ ] Record and publish a clear YouTube demo shorter than 3:00 with audio covering what was
  built and how Codex and GPT-5.6 were used.
- [ ] Review the demo for consent, private information, trademarks, and copyrighted media.
- [ ] Human-edit the Devpost description in English and map demonstrated evidence to all four
  judging criteria without claiming roadmap features.
- [x] Prepare a bounded English Devpost copy and sub-three-minute demo-script draft for human edit.
- [x] Add a fail-fast local submission preflight that keeps human/external blockers explicit.
- [x] Make submission preflight reject unpushed revisions and unresolved Devpost draft markers.
- [x] Make submission preflight reject stale first-run/tray roadmap claims after implementation.
- [x] Add a one-command locked judge verification path that cannot arm camera or OS input.
- [x] Build and independently verify an exact-revision wheel manifest and checksum from clean,
  live-remote-matched `main`; retain explicit non-standalone and unconfigured-signing limitations.
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
- [x] Harden every PowerShell entry point with shared uv resolution, frozen-lock execution,
  fail-fast native exit handling, and native Windows Qt defaults.
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
- [x] Add bounded profile import/export workflows with inactive-only import and atomic confirmed
  export replacement.

## Backlog — Phase 5

- [x] Extract normalized binocular gaze features with explicit invalid states and freshness expiry.
- [x] Build the guided nine-point calibration flow.
  - [x] Implement the bounded ordered sample-collection state machine.
  - [x] Connect collection to an in-shell Calibration UI with safe cancellation.
  - [x] Promote collection to the distraction-free full-screen presentation.
- [x] Reject per-target calibration outliers with median/MAD filtering and an absolute floor.
- [x] Implement a replaceable quadratic calibration mapper with deterministic holdout metrics.
- [x] Fit a volatile mapper after complete collection and show guarded holdout metrics in Calibration.
- [x] Add an opt-in all-or-none acceptance-policy contract with a fail-closed review-required default.
- [ ] Collect representative physical-device evidence and define justified acceptance thresholds.
- [x] Define versioned, checksummed, exact-policy persistence and fail-closed recovery for an accepted mapper.
- [x] Coordinate clear-before-save/reprovision and one-shot recovery without a Live Input dependency.
- [x] Wire accepted-mapper save/recovery without weakening Live Input startup safety.
- [x] Bind stored calibration to UTC creation time and exact physical primary-display geometry.
- [x] Add an exact-phrase replace-confirmation control that retains the saved envelope and releases
  Live Input before replacement.
- [x] Add exact-phrase, recoverable Forget saved calibration control with pipeline-first clearing.
- [x] Add an exact-phrase newest deleted-backup restore workflow with full lifecycle gates.
- [x] Run native Calibration layout QA at 900x640 and 1200x760 with top/bottom viewport inspection.
- [x] Add separate exact-phrase permanent deletion for the newest exact cataloged backup with
  path/link/type/size revalidation.
- [x] Add bounded read-only metadata cataloging for recoverably deleted calibration backups.
- [x] Add guarded repository restore with exact-record, checksum, policy, and exclusive-create gates.
- [x] Add lifecycle restore with display validation and exact-copy rollback on incompatibility.
- [x] Implement adaptive cursor smoothing as a dormant timestamp-aware One Euro domain filter.
- [x] Feed validated cursor smoothing and gate configuration into the production fake diagnostics pipeline.
- [x] Add dormant normalized-to-physical-pixel mapping for a validated primary-screen geometry.
- [x] Acquire DPI-aware primary-screen geometry through a temporary restored thread DPI scope.
- [x] Connect the accepted mapper pipeline safely using validated native geometry.
- [x] Add a dormant fail-closed freeze/resume gate for temple gestures and tracking loss.
- [x] Compose the accepted mapper, smoother, screen mapper, and movement gate in a safe,
  executor-independent candidate pipeline.
- [x] Wire a Qt-owned fake cursor diagnostics controller to lifecycle, freshness, and Diagnostics.
- [x] Construct the production candidate pipeline only after accepted calibration and native screen geometry.
- [x] Route accepted, gated cursor candidates through absolute primary-monitor `SendInput` only
  during an explicitly armed Live Input session, with fail-closed pointer-error handling.
- [x] Keep camera startup in Safe Mode and require exact-phrase, per-session consent before every
  Live Input arm while retaining every native safety preflight.
- [x] Revalidate current physical geometry against exact accepted provisioning before every native
  pointer movement and fail closed on mismatch or read failure.
- [ ] Validate broad screen reach after calibration.

## Backlog — Phase 6

- [x] Complete the non-capturing, Safe Mode first-run orientation wizard.
- [x] Complete the Dashboard, Calibration, Bindings, Profiles, Diagnostics, and Privacy views.
- [x] Complete the validated, disarm-first Sensitivity view.
- [x] Complete the stopped-only, disarm-first dedicated Camera settings/health view.
- [x] Add availability-gated system tray controls for show, pause/resume, Safe Mode, and quit.
- [x] Add profile import/export.
- [ ] Verify keyboard-only operation and visible focus.
  - [x] Add/test arrow-key shell navigation, Ctrl+1 through Ctrl+9 direct page shortcuts, focus return,
    and selected-page persistence.
  - [ ] Complete a human keyboard-only pass across native file dialogs and full-screen calibration.
- [ ] Verify Windows 100%, 125%, and 150% scaling.
- [x] Add a read-only, exclusive-create display evidence probe and capture the native 100% matrix row.
- [ ] Capture native 125% and 150% display evidence after human configuration changes.
- [ ] Verify Windows high-contrast behavior.
  - [x] Add a read-only Windows High Contrast probe and defer colors/focus to the system theme when
    enabled, with deterministic on/off/failure tests.
  - [ ] Perform and record a human visual/keyboard pass with Windows High Contrast actually enabled.
- [x] Review screens against [`../DESIGN.md`](../DESIGN.md); retain the separately listed human
  keyboard, 125%/150%, enabled High Contrast, and live-camera checks.

## Backlog — Phase 7

- [ ] Select Nuitka or `pyside6-deploy` using measured build results.
  - [x] Probe the current environment: official `pyside6-deploy` is present, while Nuitka,
    `dumpbin`, MSVC, and MinGW/GCC toolchain routes are absent.
  - [x] Define an isolated pinned standalone-first build/measurement matrix without treating tool
    availability as a selection result.
  - [ ] Provision the isolated compiler/Nuitka environment, build both comparable candidates or
    record a hard incompatibility, and select from measured results.
- [x] Bundle verified MediaPipe models and provenance in the Python wheel.
- [x] Add installed-wheel version and integrity diagnostics that cannot activate GUI or native input.
- [ ] Bundle icons and remaining default resources in the selected Windows delivery.
  - [x] Add an original token-based SVG application icon, Qt window/tray wiring, exact integrity
    tests, and installed-wheel packaging.
  - [ ] Derive/verify ICO or MSIX icon sizes after selecting the standalone Windows packager.
- [ ] Add startup and packaging error recovery.
  - [x] Add a fail-fast, non-overwriting exact-revision wheel/manifest build with full preflight.
  - [ ] Add standalone executable/installer startup recovery after a packager is selected.
- [x] Document application signing requirements.
- [ ] Run a clean-machine smoke test.
- [x] Complete privacy and troubleshooting documentation.
- [x] Profile safe synthetic performance and optimize only measured bottlenecks.
  - [x] Add a bounded JSON synthetic profile for real local model initialization/inference that
    cannot activate camera, GUI, hotkey, or operating-system input.
  - [x] Record the probe from a clean pushed revision and retain the no-optimization decision.
- [ ] Collect representative live detected-face/hand, end-to-end preview, and sustained performance
  evidence before making live-performance claims or changing model/cadence settings.
- [ ] Complete the MVP acceptance checklist.
  - [x] Publish an evidence-mapped PASS/PARTIAL/BLOCKED matrix without converting human/hardware,
    delivery, or Devpost blockers into passing claims.
  - [ ] Complete the pending rows in [`../MVP_ACCEPTANCE.md`](../MVP_ACCEPTANCE.md) before declaring a
    standalone MVP release.

## Deferred after MVP

- [ ] Multi-monitor calibration.
- [ ] Advanced ONNX gaze estimation.
- [ ] Per-application profiles and automatic switching.
- [ ] Drag-and-drop, dwell-click, and additional gestures.
- [ ] macOS and Linux input backends.
- [ ] Optional native optimization for measured hot paths.
