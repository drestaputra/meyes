# Changelog

All notable changes to MEYES will be documented in this file. Detailed implementation notes are stored in [`docs/changelog/`](./docs/changelog/README.md).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project intends to use semantic versioning once distributable builds begin.

## [Unreleased]

### Fixed

- Replaced the nearly empty completed-calibration screen with a centered result summary, readable
  quality evidence, plain-language acceptance guidance, and one safe return action; default temple
  bindings now label right/up and left/down directions explicitly.
- Removed the remaining typed/checkbox confirmation controls from Live Input, Profiles, and
  first-run completion in favor of cancel-default modal dialogs while retaining all controller and
  lifecycle safety gates.
- Fixed app-themed confirmation dialogs and tooltips to use an explicit light surface with readable
  foreground colors instead of inheriting a dark native surface behind dark text.

### Added

- Added start-only calibration onboarding: a successful uncalibrated camera start enters the guided
  full-screen flow, while resume and usable accepted calibration remain uninterrupted.
- Replaced all four Calibration management phrase inputs with direct action buttons and
  cancel-default confirmation dialogs without weakening lifecycle/revalidation boundaries.
- Clarified release-manifest signing evidence: wheels now report Authenticode as not applicable,
  preserve the raw Windows probe result, and explicitly record that code signing is not configured.
- Recorded a clean, live-remote-matched release build with an independently verified revision,
  wheel checksum, checksum file, manifest schema, and signing metadata.
- Added a Safe-Mode-first troubleshooting guide covering installation, camera/model health,
  calibration provenance, Live Input recovery, local files, and privacy-aware issue reports.
- Added a frozen, non-capturing installation-diagnostic launcher with the shared uv fallback.
- Documented fail-closed Windows signing requirements, key isolation, post-sign verification, and
  the still-open human choices without claiming the current wheel is signed.
- Replaced the stale top-bar tracking placeholder with contextual camera controls and fixed the
  minimum-size Dashboard overlap found by a native nine-page design review.
- Added a bounded synthetic JSON performance probe for real Face/Hand Landmarker initialization and
  inference without activating camera, Qt, hotkeys, or operating-system input.
- Recorded exact-revision synthetic Face/Hand timings and retained the existing worker/cadence
  design because the blank-frame profile did not justify an algorithmic optimization.
- Added an evidence-mapped MVP acceptance matrix that keeps source success separate from pending
  human/hardware, standalone delivery, and external Devpost completion.
- Added an original token-based SVG app icon with Qt window/tray wiring and exact installed-wheel
  size/checksum verification.
- Recorded a non-mutating Windows packager prerequisite spike and kept selection blocked until an
  isolated compiler/Nuitka environment can produce comparable measured builds.
- Added repository-wide verification for local links in tracked Markdown to the deterministic
  quality and submission gates.
- Added pinned Windows GitHub Actions verification for the frozen safe source and wheel judge gate.
- Removed first-run Windows CI drift by forcing LF for the checksummed SVG and making calibration
  target assertions relative to the runner's actual exposed content geometry.
- Recorded the first passing exact-revision Windows CI source/test/wheel run with explicit managed-
  runner and non-live limitations.
- Added a deterministic 10-size Windows ICO derived from the original SVG, with byte-for-byte
  regeneration, container/frame tests, and installed-wheel integrity verification.
- Added an operator-ready sub-three-minute demo runbook with explicit Safe Mode, calibration,
  fallback, privacy/rights, evidence-claim, and final human submission gates.
- Initial Python 3.11 project configuration using `uv`.
- PySide6 application shell following the MEYES design baseline.
- Typed Pydantic configuration with atomic persistence and corrupt-file recovery.
- Structured JSON rotating-file logging.
- Ruff, mypy, pytest, and PowerShell development workflows.
- OpenCV camera backend and bounded device enumeration.
- Thread-safe latest-frame-only buffer and rolling FPS measurement.
- Validated camera lifecycle state machine with pause, recovery, and deterministic shutdown.
- Webcam-free camera worker tests, including blocked-read shutdown recovery.
- Responsive camera dashboard with asynchronous discovery and device selection.
- Preview-only mirroring that leaves processing coordinates unchanged.
- Start, pause, resume, and stop controls with textual camera health and FPS.
- Camera preference persistence and clean window-close shutdown.
- Native Windows visual QA and physical webcam/controller smoke tests.
- Official local MediaPipe Face Landmarker asset with recorded SHA-256 integrity.
- Framework-independent face observations with independent eye openness and iris centers.
- Latest-frame face inference worker with health, FPS, latency, and shutdown reporting.
- Semantic gesture event domain and central gesture engine.
- Hysteretic left/right wink state machine with both-eye blink suppression.
- Configurable minimum/maximum duration, cooldown, synchronization window, and tracking timeout.
- Recorded normalized observation fixtures for deterministic gesture regression tests.
- Qt vision controller that coordinates camera frames, face inference, and semantic gesture events.
- Live Safe Mode diagnostics with face status, eye openness, inference health, latency, and recent wink events.
- Placeholder navigation pages that preserve the complete Hallmark-inspired application information architecture.
- End-to-end physical webcam-to-MediaPipe smoke verification with deterministic worker shutdown.
- Official local MediaPipe Hand Landmarker asset with checksum verification and native initialization smoke test.
- Framework-independent hand observations for up to two hands with anatomical handedness and 21 landmarks.
- Centralized conversion from MediaPipe selfie labels and mirrored coordinates into canonical processing space.
- Lower-cadence hand inference worker with wall-clock scheduling and latest-frame processing.
- Lifecycle result gates that discard in-flight face or hand inference after suspend and stop.
- Retry-safe vision controller shutdown that retains a worker reference after a timeout.
- Actual camera-frame dimensions on normalized face and hand observations.
- Bounded capture-time pairing of lower-cadence hands with fresh face history.
- Aspect-correct, face-width-normalized index-fingertip distance to anatomical temple anchors.
- Explicit unavailable, stale, skewed, invalid, out-of-order, and expired temple-feature states.
- Qt-safe composition of face and lower-cadence hand workers with coalesced, generation-gated result and health delivery.
- Watchdog-driven temple-feature expiry using the configured tracking timeout, including late face/hand re-pairing.
- Live Safe Mode diagnostics for hand health, detected-hand count, feature availability, and left/right temple-distance ratios.
- OpenAI Build Week submission record, judge quickstart, build-period evidence, source and model licensing notices, and precise runtime privacy disclosures.
- Configurable temple enter/exit ratios and stabilization timing.
- Framework-independent, per-side Near/Far/Unknown temple proximity hysteresis with strict ordering, malformed-input, and tracking-timeout guards.
- Transition-only proximity signals and live state labels in Safe Mode Diagnostics, with operating-system actions disconnected.
- Configurable `550 ms` temple hold threshold and `250 ms` post-interaction cooldown.
- Framework-independent, independently armed left/right temple tap and hold state machines using fresh capture-time evidence.
- Semantic tap, hold-start, and exactly-once hold-end events in Diagnostics, including timeout, pause, and shutdown termination without bindings or OS input.
- Closed, discriminated MVP action vocabulary with bounded scroll, supported-key, shortcut, and hold-only continuous-action validation.
- Complete logical binding profiles, exact built-in defaults, phased hold-event resolution, and fail-closed user profile persistence.
- Platform-neutral input protocol plus an in-memory fake executor; no Windows input backend is connected.
- Fake-only, poll-driven action dispatcher with per-producer at-most-once ordering, stable hold snapshots, shared-button ownership, no-catch-up continuous scheduling, lifecycle gating, and retryable release-all fault recovery.
- Qt-owned action simulation that loads the active profile fail-closed, consumes live semantic events, schedules dispatcher deadlines without a worker loop, releases before camera shutdown, and exposes bounded fake primitive diagnostics in a responsive Safe Mode layout while OS input remains disconnected.
- Durable Profiles workflow with all-disabled creation, pause-first activation, preference rollback, canonical active-profile status, and a read-only preview of all six simulated bindings.
- Isolated Bindings editor covering every validated MVP action with hold-only filtering, inline errors, last-valid preview, dirty-draft preservation, and inactive save-as-copy.
- Fail-safe inactive profile lifecycle with rename, modal-confirmed recoverable deletion, restore-from-Default, and built-in/active-profile protections.
- Dormant Windows `SendInput` executor for validated mouse and keyboard primitives with ABI-safe ctypes structures, owned held-state tracking, partial-send detection, reverse-order cleanup, and fake native-boundary tests.
- Dormant Windows live-safety foundation with `Ctrl+Alt+Shift+F11` registration, native Qt hotkey filtering, retryable cleanup, and physical button/modifier preflight.
- Dormant explicit-consent live session controller with hotkey-first preflight, lazy `SendInput` construction, release-first arming, emergency disarm, profile-transition gating, and terminal cleanup.
- Application-wired Live Input view with volatile modal consent, real `SendInput` dispatch, persistent Safe/Live/Fault status, native emergency pause, physical-input preflight, camera/profile lifecycle disarm, pending-profile recovery, and terminal release paths.
- Accepted-calibration gaze pointer output using primary-monitor absolute `SendInput` coordinates, armed-session gating, cursor-pipeline lifecycle gates, and release-plus-tracking-pause recovery on native movement failure.
- Explicit-consent-only Live Input arming after camera startup, retaining global emergency-hotkey registration, physical-input checks, release-first activation, and fresh modal consent after every disarm.
- Per-movement physical-display provenance revalidation against the exact active cursor provisioning, with pipeline invalidation and fail-closed Live Input recovery on mismatch or native read failure.
- Modal-confirmed saved-calibration replacement that retains the previous envelope until confirmation, keeps the accepted candidate pipeline volatile while pending, and requires Live Input release before the write.
- Exact-record permanent deletion for the newest recoverable calibration backup, guarded by a separate destructive modal, bounded catalog membership, path/link/type/size revalidation, and no runtime-state change.
- Read-only, exclusively written Windows display-scaling evidence probe covering native physical geometry, system DPI, Qt logical geometry/DPR, and two consistency checks; native 100% evidence is recorded while 125%/150% remain pending.
- Fresh-clone locked dependency, package entry-point, static-analysis, and 740-test verification in an isolated CPython 3.11 environment on the same Windows 11 host, with second-machine/live limitations recorded.
- Shared fail-fast PowerShell uv resolver with direct-launcher and `python -m uv` support, frozen-lock execution across all scripts, and native Qt testing unless callers explicitly request another platform.
- Non-mutating local submission preflight for branch, origin, clean worktree, required tracked evidence files, MIT/readme invariants, and optional full gate, with human/external blockers always reported separately.
- Optional live remote-revision parity and unresolved-draft-marker checks in submission preflight, with revision-stable Devpost verification copy.
- One-command judge source verification for frozen dependency sync, package entry-point import, and the full deterministic gate without camera or OS-input activation.
- Wheel-safe MediaPipe asset bundling with packaged-first/source-fallback resolution and isolated installed-artifact integrity verification.
- Standard-library-only `--version` and JSON `--diagnose-install` commands for installed Python/platform/model verification without importing Qt or activating hardware/native input.
- Read-only, scrollable Privacy view with explicit camera/storage/network/native-input boundaries, current Safe/Live state, and selectable local file locations.
- Validated Sensitivity view with dirty drafts/default staging, disarm-first persistence, and fail-closed accepted-pipeline reconstruction for One Euro and temple-gate settings.
- Dedicated Camera settings/health view with stopped-only complete capture updates, disarm-first persistence, Dashboard synchronization, dirty/default staging, and no duplicate start control.
- Keyboard-first shell navigation with arrow keys, Ctrl+1 through Ctrl+9 page shortcuts, focus return, and fail-safe selected-page persistence.
- Three-step first-run orientation for privacy, camera readiness, calibration honesty, and Safe Mode, with no capture/output side effects and modal-confirmed durable completion.
- Availability-gated system tray with truthful camera/input status and bounded Show, Pause/Resume, Return to Safe Mode, and Quit actions while preserving full close shutdown.
- Read-only Windows High Contrast detection that defers color/focus rendering to the native system theme while preserving explicit non-color safety text.
- Submission truthfulness refresh for newly completed first-run, Camera/Sensitivity, Privacy, keyboard, High Contrast, and tray scope, with stale-roadmap preflight rejection.
- Non-overwriting exact-revision wheel release builder gated by clean live-remote parity and full judge verification, with SHA-256 plus explicit unsigned/non-standalone manifest limitations.
- Safe profile JSON transfer with a 256 KiB import bound, duplicate-key/schema validation, inactive collision handling, strict repository reads, exclusive/atomic export, native file dialogs, and Live Input disarm before modal dialog entry.
- Fail-closed binocular gaze feature extraction using pixel-aspect-correct eye-local axes, explicit invalid states, Qt lifecycle expiry, and uncalibrated Diagnostics values without pointer output.
- Dormant bounded nine-point calibration collector with volatile per-target quotas, attempt caps, ordered-frame replay guards, feature bounds, binocular-consistency checks, retry, cancel, and reset semantics.
- User-facing in-shell Calibration collection with explicit target arming, progress/retry controls, Live Input release-before-start, and volatile cancellation on Escape, navigation away, camera loss, Live Input arming, or shutdown.
- Robust per-target calibration outlier rejection using coordinate-wise median/MAD bounds, a zero-MAD floor, inlier-only quotas, bounded attempts, and explicit UI feedback.
- Replaceable quadratic calibration mapper with complete-target coverage, finite/rank/conditioning guards, unclamped prediction, deterministic target-stratified holdouts, and normalized error metrics.
- Guarded user-triggered volatile calibration fitting after all nine targets, with recoverable numerical-failure feedback and honest holdout metrics in the Calibration UI while pointer output remains disconnected.
- Opt-in all-or-none calibration acceptance policy with transparent multi-limit rejection reasons, a fail-closed `Review Required` default, accepted-result isolation, and no mapper activation or persistence.
- Distraction-free primary-display calibration presentation with normalized nine-point target placement, keyboard controls, live progress/fit feedback, return-after-completion, and fail-safe close/lifecycle cancellation.
- Dormant configurable One Euro 2D filter with velocity-adaptive cutoff, strict monotonic timestamps, stale-gap reseeding, independent axes, and deterministic jitter/responsiveness replay tests.
- Dormant primary-screen coordinate mapper with explicit physical-pixel geometry, inclusive endpoints, per-axis clamping evidence, signed 32-bit bounds, and no executor dependency.
- Dormant fail-closed cursor movement gate with tracking suspension, overlapping temple holds, tap pulses, monotonic ordering, configurable resume delay, and no output consumer.
- Proof-carrying accepted-calibration token and fake-only cursor pipeline composing calibration, smoothing, screen mapping, and movement gating without an input executor.
- Qt-owned fake cursor diagnostics with separate capture/delivery clocks, freshness expiry, lifecycle/event wiring, candidate display, and an honest unavailable production default.
- Read-only Windows primary-monitor geometry acquisition using a temporary restored Per-Monitor V2 DPI scope, physical-pixel `GetMonitorInfoW` bounds, fake native-boundary tests, and fail-closed validation.
- Acceptance-gated production provisioning for the fake-only cursor diagnostics pipeline, with lazy geometry reads, persistent unavailable reasons, automatic calibration-loss teardown, and no executor dependency.
- Versioned accepted-calibration evidence repository with canonical SHA-256 checksums, exact-policy recovery, bounded strict JSON, atomic replacement, recoverable invalid-file quarantine, and link/reparse refusal; runtime save/load remains disconnected.
- Disconnected accepted-calibration persistence lifecycle with clear-before-save ordering, volatile fallback after storage failure, one-shot startup recovery, quarantine reporting, and fake-only reprovisioning.
- Composition-root accepted-calibration save/recovery using shared application paths, SAFE-only startup invariants, sanitized Calibration status/logging, and conditional fake diagnostics provisioning without consent or executor restoration.
- Config-driven fake cursor provisioning for One Euro smoothing and temple/tracking gate settings, with behavioral tests for custom resume delay and filter response.
- Accepted-calibration schema 2 provenance with canonical UTC creation time, physical primary-display geometry, legacy-schema preservation, startup geometry mismatch invalidation, and sanitized provenance UI.
- Modal-confirmed Forget saved calibration workflow with pipeline-first clearing, recoverable timestamped backup moves, sanitized status/logging, and no Live Input state change.
- Read-only bounded deleted-calibration backup catalog metadata with strict filename timestamps, newest-first ordering, link/reparse refusal, and no payload reads or mutations.
- Guarded repository restore for exact deleted-calibration catalog records with full envelope revalidation, exclusive active creation, no active overwrite, and retained backups on success or failure.
- Calibration restore lifecycle with pipeline-first clearing, current-display reprovision validation, byte-matched active-copy rollback, and retained deleted backups.
- Modal-confirmed newest calibration-backup restore UI with bounded timestamp/size metadata, full lifecycle validation, sanitized status/logging, and unchanged Live Input state.
- Native Calibration-page vertical scrolling with preserved control size hints, no horizontal scrolling, ASCII-safe backup metadata, and visual QA at 900x640 and 1200x760.
