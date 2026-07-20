# Changelog

All notable changes to MEYES will be documented in this file. Detailed implementation notes are stored in [`docs/changelog/`](./docs/changelog/README.md).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project intends to use semantic versioning once distributable builds begin.

## [Unreleased]

### Added

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
- Fail-safe inactive profile lifecycle with rename, exact-name-confirmed recoverable deletion, restore-from-Default, and built-in/active-profile protections.
- Dormant Windows `SendInput` executor for validated mouse and keyboard primitives with ABI-safe ctypes structures, owned held-state tracking, partial-send detection, reverse-order cleanup, and fake native-boundary tests.
