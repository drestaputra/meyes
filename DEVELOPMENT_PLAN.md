# MEYES Development Plan

Status: planning baseline  
Target: Windows 10/11 desktop MVP  
Primary specification: [`MEYES_CODEX_SPEC.md`](./MEYES_CODEX_SPEC.md)  
Design reference: [nutlope/hallmark](https://github.com/nutlope/hallmark)

Execution checklist: [`docs/TODO.md`](./docs/TODO.md)  
Dated development log: [`docs/changelog/`](./docs/changelog/README.md)

## 1. Product outcome

MEYES must become a safe, local-first Windows accessibility application that lets a user:

1. calibrate eye gaze with a standard webcam;
2. move the pointer with gaze;
3. trigger independent click actions with left/right winks;
4. trigger tap/hold actions near the left/right temple;
5. expose independent left/right cheek-touch gestures as optional bindings;
6. pause all tracking immediately from the UI, tray, or emergency shortcut;
7. change gesture bindings without changing vision code.

The first release is an assistive productivity tool, not a medical device. Accuracy claims will be based on measured tests, not marketing assumptions.

## 2. Planning assumptions

- One Windows-first codebase using Python 3.11, PySide6, OpenCV, MediaPipe, Pydantic, and Win32 `SendInput`.
- Camera frames and biometric observations remain local by default.
- The primary monitor is supported first; multi-monitor calibration is deferred.
- Phase 0 and Phase 1 form the first implementation batch.
- Calendar estimates are intentionally deferred until camera capture, packaging, and MediaPipe performance are measured on at least two representative Windows devices.
- Every phase ends with tests, static checks, a `CHANGELOG.md` update, and a short limitations report.

## 3. Non-negotiable engineering decisions

### Safety boundary

Vision code emits observations only. Gesture state machines turn observations into semantic events. The binding layer maps events to actions. Only the Windows input backend may inject OS input.

```text
Camera -> Observations -> Gesture events -> Bindings -> Action executor
```

No gesture detector may call mouse or keyboard APIs directly.

### Freshness over completeness

- Camera and vision exchange a single latest frame, not an unbounded queue.
- All observations use monotonic timestamps.
- Stale face or hand observations are rejected.
- Continuous input ends on timeout, pause, camera failure, tracking loss, or shutdown.

### Testability

- State machines, bindings, configuration, calibration mapping, and filters must work without a webcam.
- Recorded normalized observations are fixtures for gesture regression tests.
- OS input is replaceable with a fake executor in tests.
- Live gesture testing starts in a no-input safety mode.

## 4. Product workstreams

| Workstream | Outcome | First proof |
|---|---|---|
| Application shell | Responsive native UI, tray lifecycle, deterministic shutdown | Window opens and closes without orphan workers |
| Camera platform | Selectable, recoverable webcam pipeline | Stable mirrored preview with measured FPS |
| Vision observations | Face, eye, iris, hand, and temple features | Live diagnostics with no OS action |
| Gesture semantics | Debounced wink and tap/hold events | Recorded fixtures pass deterministic tests |
| Input safety | Validated configurable Windows actions | Test mode and fake executor pass before live input |
| Gaze calibration | Screen mapping with smoothing | Live pursuit path reaches all broad screen regions |
| Settings and profiles | Persistent, recoverable local configuration | Round-trip, migration, and corrupt-file tests pass |
| Packaging and privacy | Installable local-only Windows build | Clean-machine smoke test and privacy notice |

## 5. Delivery roadmap

### Phase 0 — Repository foundation

Deliverables:

- `pyproject.toml` and `src/meyes` package layout;
- application entry point and basic PySide6 shell;
- typed configuration models and safe path helpers;
- rotating structured logs;
- Ruff, Pyright or mypy, and pytest configuration;
- PowerShell development scripts;
- README, changelog, and contribution conventions.

Exit criteria:

- `python -m meyes` opens a native window;
- unit tests, lint, and type checks pass;
- startup and shutdown are logged;
- invalid configuration falls back safely.

### Phase 1 — Camera vertical slice

Deliverables:

- camera enumeration and selector;
- OpenCV capture worker;
- latest-frame-only transport;
- mirrored preview independent of processing coordinates;
- measured capture/preview FPS;
- start, pause, resume, stop, reconnect, and shutdown behavior;
- camera health state visible in the dashboard.

Exit criteria:

- UI remains usable while capture runs;
- switching cameras does not leak handles or threads;
- disconnecting a camera produces a recoverable state;
- no MediaPipe dependency is introduced yet.

### Phase 2 — Face, gaze features, and wink events

Deliverables:

- MediaPipe Face Landmarker adapter;
- normalized face and eye observations;
- independent eye-openness values;
- both-eye blink suppression;
- wink state machine, cooldown, and event diagnostics;
- per-user adjustable sensitivity.

Exit criteria:

- both-eye blinks do not emit left/right wink events in ordinary tests;
- one sustained wink emits at most one event;
- tests run from recorded observations without a camera;
- OS input remains disabled.

### Phase 3 — Hand and temple state machines

Deliverables:

- MediaPipe Hand Landmarker adapter at a lower inference cadence;
- one canonical handedness/mirroring conversion;
- temple and cheek anchors with face-width-normalized distance;
- hysteresis, stabilization, tap, hold-start, and hold-end states;
- observation timeout and tracking-loss recovery.

Exit criteria:

- tap emits only after release;
- hold start emits once and always receives an end event;
- tracking loss ends a hold within the configured timeout;
- wrong-hand/wrong-side face-touch sequences are rejected;
- stable cheek touches emit once on release and never click on startup or tracking loss.

### Phase 4 — Bindings and Windows input

Deliverables:

- Pydantic discriminated action models;
- default and user profile repositories;
- Windows `SendInput` implementation behind `InputExecutor`;
- mouse click, scroll, continuous scroll, shortcut, and tracking actions;
- global emergency pause shortcut;
- no-input test mode and release-all fail-safe.

Exit criteria:

- every gesture can be disabled or rebound;
- unsupported keys/actions fail validation;
- pause, failure, and shutdown release all synthetic input states;
- automated tests use a fake executor, never the live OS backend.

### Phase 5 — Gaze calibration and cursor control

Deliverables:

- gaze feature extraction;
- hands-free Smooth Pursuit live capture with synchronized target positions, region coverage,
  following-correlation evidence, and robust residual fitting;
- replaceable calibration mapper;
- One Euro or equivalent adaptive filter;
- pointer mapping to the primary screen;
- cursor freeze/resume around temple interactions.

Exit criteria:

- a completed calibration reaches all broad screen regions;
- face loss freezes the pointer at its last location;
- smoothing improves jitter without unacceptable lag;
- calibration can be replaced and recovered safely.

### Phase 6 — Complete product UI

Deliverables:

- first-run setup wizard;
- Dashboard, Calibration, Bindings, Sensitivity, Camera, Profiles, Diagnostics, and Privacy views;
- system tray controls;
- keyboard navigation, focus visibility, scalable text, and non-color status cues;
- profile import/export and restore defaults.

Exit criteria:

- the MVP can be configured without editing JSON;
- setup validates gestures before live input is enabled;
- every main workflow is keyboard-operable;
- the UI follows [`DESIGN.md`](./DESIGN.md).

### Phase 7 — Packaging and hardening

Deliverables:

- Nuitka or `pyside6-deploy` packaging decision based on measurement;
- signed-build path documented, even if signing is not yet available;
- model/resource bundling;
- clean-machine smoke checklist;
- privacy, troubleshooting, and recovery documentation;
- performance profiling and only measured optimizations.

Exit criteria:

- packaged app launches on a clean supported Windows machine;
- camera/model/config failures remain recoverable;
- no frames are stored or sent by default;
- all MVP acceptance criteria in the specification are checked.

## 6. First execution batch: Phase 0 + Phase 1

Implementation order:

1. Bootstrap package, quality tools, logging, paths, and configuration.
2. Create application state models and a minimal main window.
3. Implement camera interface, device enumeration, and health states.
4. Implement capture worker and latest-frame container.
5. Wire Qt signals to preview, controls, and FPS/health indicators.
6. Add deterministic pause, stop, reconnect, and shutdown behavior.
7. Add configuration and camera-state unit tests.
8. Run checks, update changelog, and document limitations.

Phase 0/1 is complete only when the application is runnable. Empty scaffolding is not a deliverable.

## 7. Design integration

Hallmark is attached as a design methodology and quality gate, not as UI code to copy. MEYES uses these parts of its approach:

- structure follows the product's single job rather than a generic dashboard template;
- all colors, type roles, spacing, radii, and motion are locked as named tokens;
- copy remains factual and contains no invented accuracy or performance claims;
- every interactive component has explicit default, hover, focus, active, disabled, loading, error, and success behavior where applicable;
- the interface is reviewed for hierarchy, restraint, specificity, accessibility, and visual sameness before handoff;
- decorative chrome, excessive pills, gradients, and repeated card grids are avoided.

The native desktop interpretation is defined in [`DESIGN.md`](./DESIGN.md).

## 8. Verification strategy

### Automated gates

- `ruff check .`
- `ruff format --check .`
- selected type checker over `src` and tests;
- `pytest` with unit and integration markers;
- deterministic fixture tests for gesture state machines;
- configuration round-trip, migration, and recovery tests.

### Manual gates

- camera lifecycle and disconnect/reconnect;
- normal/dim lighting, glasses, face movement, and both hands visible;
- wrong hand near temple and hand leaving frame during hold;
- pause/exit while continuous input is active;
- 100%, 125%, and 150% Windows scaling;
- keyboard-only navigation and Windows high-contrast mode;
- packaged build on a machine without the development environment.

## 9. Risk register

| Risk | Impact | Early mitigation | Decision gate |
|---|---|---|---|
| Commodity webcam gaze accuracy | Cursor may feel unreliable | Lightweight calibration, filtering, honest acceptance targets | Measure after Phase 5 before advanced models |
| Wink/blink confusion | Accidental clicks | Independent thresholds, sync window, cooldown, no-input setup test | Phase 2 fixture and manual test gate |
| Lost hand during hold | Endless scroll/key state | Timeouts and unconditional `release_all()` | Phase 3/4 fail-safe tests |
| CPU load from face + hand models | UI lag and stale input | Latest-frame buffer, lower hand cadence, profile first | Benchmark before native optimization |
| Camera/model packaging | Clean-machine startup failure | Package a minimal camera slice early | Packaging spike after Phase 1 |
| Qt custom styling harms accessibility | Poor focus/high-contrast behavior | Tokenized palette, native semantics, keyboard QA | UI audit in every phase |
| Config evolution breaks users | Lost bindings/calibration | Versioned Pydantic models, backups, migrations | Migration tests before Phase 7 |

## 10. Release checkpoints

| Checkpoint | Evidence required |
|---|---|
| Developer preview | Phase 0/1 checks pass; camera preview is stable |
| Gesture preview | Phase 2/3 diagnostics work with OS input disabled |
| Controlled alpha | Phase 4/5 complete; emergency pause and fail-safes verified |
| MVP candidate | Phase 6 complete; full workflows and privacy copy present |
| MVP release | Phase 7 clean-machine and acceptance checklist complete |

## 11. Immediate next task

Implement Phase 0 and Phase 1 as one runnable vertical slice. Do not add MediaPipe until camera lifecycle, configuration recovery, logging, and deterministic worker shutdown are stable.
