# MEYES

MEYES is a Windows-first local vision application exploring hands-free computer interaction with an ordinary webcam. The current OpenAI Build Week build runs independent face and hand landmark pipelines, derives binocular iris positions, detects left/right wink events, calculates same-side fingertip-to-temple distance, stabilizes independent Near/Far/Unknown states, and classifies per-side tap, hold-start, and hold-end events. The application opens in Safe Mode and keeps an in-memory action trace. On Windows, a user can explicitly opt in per session to calibrated gaze pointer movement plus configured click, scroll, key, and shortcut actions through `SendInput` after the emergency-hotkey, physical-input, and release preflights pass.

The product controls are gaze-driven pointer movement, wink clicks, and temple-gesture scrolling with configurable bindings. Validated defaults and a Qt-owned fake dispatcher exercise gesture mappings in tests and Diagnostics. The Profiles view can create and safely activate durable profiles; rename, restore, or recoverably delete protected inactive profiles; and import/export complete validated JSON snapshots without activating them. Bindings provides inline editing for every validated MVP action, an isolated six-row preview, and save-as-copy without runtime activation. Sensitivity edits validated smoothing and temple-gate settings, releases Live Input before saving, and rebuilds only a still-valid accepted cursor pipeline. A dedicated Camera view reports capture health and edits complete requested capture settings only while stopped; Dashboard retains device selection, preview, and lifecycle controls. The Live Input view owns the deliberate real-output transition: exact typed consent, global emergency-hotkey registration, physical-input preflight, release-first arming, visible status, and release on emergency, disarm, camera pause/fault, profile change, file dialog, or shutdown. Pointer candidates are emitted only from an accepted, display-matched calibration and are ignored unless Live Input is explicitly armed. A read-only Privacy view exposes current Safe/Live state, storage/network boundaries, and selectable local file locations.

> Status: early development. Meyes is not a medical device and should not be relied upon for safety-critical operation.

On a new local configuration, a three-step first-run orientation explains privacy, camera setup,
calibration honesty, and Live Input safety without opening a camera or enabling OS output. Completion
is recorded only after the final safety acknowledgement is explicitly selected and saved.

## Development status

Phase 0 through Phase 4 are implemented, and Phase 5 includes fail-closed normalized gaze features plus a distraction-free primary-display nine-point collection flow. Calibration fits a mapper and reports deterministic holdout metrics; acceptance defaults to `Review Required`. An executor-independent cursor pipeline composes proof-carrying accepted calibration, configured adaptive smoothing, physical-pixel mapping, and the configured tracking/temple gate. A Qt-owned diagnostics controller is wired to gaze, gesture, camera lifecycle, and freshness-clear signals. When and only when calibration is accepted, a provisioning boundary reads Windows primary-monitor physical pixels through a temporary restored Per-Monitor V2 DPI scope and constructs that pipeline. Missing acceptance, unsupported geometry, or native failure keeps Diagnostics truthfully `Unavailable` and clears any prior candidate. Accepted candidates reach the native executor only during an explicitly armed Live Input session; each move revalidates the current physical display against the exact provisioned geometry, and mismatch or native failure removes the pipeline, faults Live Input, releases owned input, and requests tracking pause. Accepted fits are atomically saved in a schema-2 checksummed evidence envelope with UTC creation time and physical primary-display geometry. A newly accepted fit cannot overwrite an existing envelope until Live Input is released and `REPLACE SAVED CALIBRATION` is typed exactly; before confirmation it remains volatile while the prior file stays intact. Safe startup recovery requires the exact same policy and geometry; mismatch keeps the stored file but removes the pipeline. Exact-phrase controls can forget the active envelope into a recoverable backup, restore the newest valid backup through checksum/policy/display revalidation, or permanently delete exactly the newest cataloged backup. These persistence paths cannot restore consent or arm Live Input. Physical-device reach evidence and scaling-matrix QA remain pending.

See:

- [`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) for the roadmap;
- [`DESIGN.md`](./DESIGN.md) for the native UI system;
- [`docs/TODO.md`](./docs/TODO.md) for the active checklist;
- [`docs/DEVPOST_DRAFT.md`](./docs/DEVPOST_DRAFT.md) for human-reviewed submission preparation;
- [`docs/changelog/`](./docs/changelog/README.md) for dated implementation records.

## OpenAI Build Week 2026

- Recommended submission category: **Apps for Your Life**; the human entrant must confirm it.
- Target platform: Windows 10/11 x64, Python 3.11, and an ordinary webcam; live and visual QA is currently recorded on Windows 11 x64.
- Build-period evidence: Git history begins on July 19, 2026, inside the July 13-21 submission window and remains unsquashed.
- Runtime boundary: GPT-5.6 and Codex helped build MEYES; neither is an application runtime dependency and no OpenAI API key is required.
- Safety boundary: the application opens and starts its camera with OS input disconnected. Live Input requires volatile exact-phrase consent; its emergency shortcut, preflight, armed state, and release behavior must be shown in any demo that uses real output.

See the [Build Week submission record](./docs/BUILD_WEEK_SUBMISSION.md) and [judge quickstart](./JUDGES.md). The public demo URL, final Devpost URL, and `/feedback` Session ID remain explicit pre-submission checklist items.

## How Codex and GPT-5.6 were used

Codex was used as the implementation partner for phase planning, typed Python/Qt development, concurrency and lifecycle review, deterministic test generation, native visual QA, physical pipeline smoke tests, and documentation. Codex accelerated repetitive implementation and adversarial race-condition review. GPT-5.6 was explicitly selected before the live face/hand composition iteration in commit `57e08f2` and is being used for subsequent implementation and Build Week readiness work.

The human author chose the local-first architecture, Safe Mode boundary, gesture vocabulary, Hallmark-inspired native design direction, phase acceptance criteria, and the policy of testing, committing, and pushing every completed iteration. The first repository iteration completed after the explicit GPT-5.6 model switch is commit [`57e08f2`](https://github.com/drestaputra/meyes/commit/57e08f2); earlier commit history is preserved rather than rewritten. The required `/feedback` Session ID will be supplied directly in the Devpost form.

## Requirements

- Windows 10 or Windows 11, 64-bit;
- Python 3.11;
- [`uv`](https://docs.astral.sh/uv/).

## Setup

```powershell
uv python install 3.11
uv sync --frozen --group dev
```

The two MediaPipe model bundles used by the source build are already present under `resources/models/`. Their official component model cards identify Apache License 2.0, and their source URLs, sizes, and SHA-256 checksums are recorded.

## Run

```powershell
uv run meyes
```

Or use:

```powershell
.\scripts\run_dev.ps1
```

## Live Input safety

1. Start the camera and verify stable gesture diagnostics in **Diagnostics**.
2. Complete an accepted calibration if you want gaze pointer movement.
3. Open **Live Input**, release physical mouse buttons and modifier keys, type
   `ENABLE LIVE INPUT` exactly, and select **Arm Live Input**.
4. Confirm the persistent bar says `LIVE INPUT` before testing in a disposable target window.
5. Press `Ctrl+Alt+Shift+F11`, select **Return to Safe Mode**, pause/stop the camera, or close MEYES
   to gate dispatch and release all input owned by MEYES.

Consent and armed state are not persisted. Every disarm, including a profile change, requires the
exact phrase again.
Windows may block `SendInput` when the target process runs at a higher integrity level; MEYES
cannot bypass that operating-system boundary. Automated tests use fake native APIs and never send
real input.

## Verify

```powershell
.\scripts\check.ps1
```

The check script runs formatting verification, linting, type checking, and tests.
PowerShell entry points resolve a direct `uv` launcher first, fall back to `python -m uv`, use the
committed lockfile in frozen mode, and report one actionable prerequisite error if neither is
available. Qt tests use the native Windows platform unless the caller explicitly sets
`QT_QPA_PLATFORM`.

Run the non-mutating local submission audit with:

```powershell
.\scripts\submission_preflight.ps1 -VerifyRemote -RunFullCheck
```

It checks local Git/file/evidence invariants, confirms the exact revision is present on
`origin/main`, and then prints the human/external blockers it cannot verify. It never submits to
Devpost or changes repository visibility.

Judges can reproduce the locked source setup, package entry-point smoke test, and full deterministic
gate without opening a camera or arming OS input:

```powershell
.\scripts\judge_verify.ps1
```

For a JSON install/model-integrity check that does not import Qt or activate hardware/native input:

```powershell
.\scripts\diagnose_install.ps1
```

Profile the real local model adapters on a bounded synthetic blank frame without opening a camera,
Qt, an emergency hotkey, or OS input:

```powershell
.\scripts\profile_safe.ps1
```

The JSON timings are specific to the current host/load/runtime and are not evidence of live camera
accuracy, detected-face/hand latency, or end-to-end throughput.
The latest clean-revision synthetic result and no-optimization decision are recorded in
[`docs/evidence/performance/2026-07-21.md`](./docs/evidence/performance/2026-07-21.md).

Build a non-overwriting, exact-revision Python wheel handoff with SHA-256 and an honest unsigned
artifact manifest only after clean remote parity and the full judge gate pass:

```powershell
.\scripts\build_release.ps1
```

This produces a wheel, not a standalone executable or installer, and does not publish the artifact.
The latest clean-revision build and independent checksum verification are recorded in
[`docs/evidence/release/2026-07-21.md`](./docs/evidence/release/2026-07-21.md).
Requirements for a future signed Windows executable/package are documented separately in
[SIGNING.md](./SIGNING.md); no certificate or signing pipeline is currently configured.
The measured local packager/toolchain blocker and standalone-first comparison plan are recorded in
[`docs/evidence/packaging/2026-07-21.md`](./docs/evidence/packaging/2026-07-21.md).

Capture a new, non-overwriting Windows display-scaling evidence record with:

```powershell
.\scripts\capture_display_evidence.ps1 -OutputPath docs\evidence\display\YYYY-MM-DD-SCALE-percent.json
```

The current evidence matrix is documented in
[`docs/evidence/display/`](./docs/evidence/display/README.md).

A fresh-clone, isolated-environment source check is recorded in
[`docs/evidence/clean-source/2026-07-21.md`](./docs/evidence/clean-source/2026-07-21.md).

The evidence-mapped release decision, including every remaining human/hardware and delivery blocker,
is maintained in [MVP_ACCEPTANCE.md](./MVP_ACCEPTANCE.md).

The main navigation supports arrow keys and Ctrl+1 through Ctrl+9 in the displayed page order;
shortcut activation returns focus to the navigation list.

When the Windows desktop reports system-tray support, MEYES adds bounded Show, Pause/Resume,
Return to Safe Mode, and Quit actions. Closing the main window still performs the normal full
shutdown; this build does not silently change close into background execution.

MEYES reads the Windows High Contrast preference without changing it. When enabled, the application
does not apply its custom color stylesheet and instead uses the system Qt/Windows palette and native
focus rendering; all safety states remain explicit text rather than color-only indicators.

No webcam is required for the deterministic test suite. A webcam is required only for the live camera and model path.

No external sample dataset is required. Deterministic normalized observation fixtures are
included under `tests/fixtures/observation_sequences/`.

## Local data

Meyes uses Windows-appropriate per-user locations:

- configuration: `%APPDATA%\Meyes\config.json`;
- logs: `%LOCALAPPDATA%\Meyes\Logs\meyes.log`;
- accepted-calibration evidence envelope: `%LOCALAPPDATA%\Meyes\accepted-calibration.json` when a
  fitted mapper passes every explicitly configured acceptance limit;
- other local data: `%LOCALAPPDATA%\Meyes\`.

MEYES does not intentionally persist or transmit camera frames. MediaPipe performs input-media processing on-device, while Google's current MediaPipe terms state that Solution APIs may periodically contact Google and send non-input usage, performance, application, and system metrics. See [PRIVACY.md](./PRIVACY.md) for the precise boundary.

For safe recovery from setup, camera, model, calibration, display, or Live Input failures, see
[TROUBLESHOOTING.md](./TROUBLESHOOTING.md).

## Design reference

The native design system uses the MIT-licensed [nutlope/hallmark](https://github.com/nutlope/hallmark) project as a review methodology and anti-generic design reference. No Hallmark code, generated page, screenshot, or asset is copied into MEYES; the application defines its own PySide6 information architecture and visual tokens.

## License and third-party components

Original MEYES code and documentation are licensed under the [MIT License](./LICENSE). Third-party libraries and model assets retain their upstream terms; their provenance, model-card licenses, and distribution notes are recorded in [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).
