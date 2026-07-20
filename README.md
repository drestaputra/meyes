# MEYES

MEYES is a Windows-first local vision application exploring hands-free computer interaction with an ordinary webcam. The current OpenAI Build Week build runs independent face and hand landmark pipelines, derives binocular iris positions relative to each eye for future calibration, detects left/right wink events, calculates same-side fingertip-to-temple distance, stabilizes independent Near/Far/Unknown states, and classifies per-side tap, hold-start, and hold-end events. Safe Mode remains the default and keeps an in-memory action trace. On Windows, the user can explicitly opt in per session to send the configured click, scroll, key, and shortcut actions through `SendInput`.

The planned product controls are gaze-driven pointer movement, wink clicks, and temple-gesture scrolling with configurable bindings. Validated defaults and a Qt-owned fake dispatcher exercise those mappings in tests and in Diagnostics. The Profiles view can create and safely activate durable profiles; rename, restore, or recoverably delete protected inactive profiles; and import/export complete validated JSON snapshots without activating them. Bindings provides inline editing for every validated MVP action, an isolated six-row preview, and save-as-copy without runtime activation. The Live Input view owns the deliberate transition to real OS output: exact typed consent, global emergency-hotkey registration, physical-input preflight, release-first arming, visible status, and release on emergency, disarm, camera pause/fault, profile change, file dialog, or shutdown. Gaze pointer movement is not implemented.

> Status: early development. Meyes is not a medical device and should not be relied upon for safety-critical operation.

## Development status

Phase 0 through Phase 3 are complete, the bounded Phase 4 workflows are implemented, and Phase 5 has started with fail-closed normalized gaze feature extraction plus a dormant, bounded nine-point sample collector. Diagnostics shows the binocular eye-relative feature and its explicit availability state, but it is not a screen coordinate and cannot move the pointer. The collector has ordered targets, per-target quotas, attempt caps, replay guards, and basic feature-quality rejection; it is not yet connected to a user-facing Calibration flow or persistence. The durable Profiles workflow supports pause-first activation with preference rollback, inactive-only rename, confirmed recoverable deletion, restore-from-Default, and bounded schema-validated import/export. Imports are always new inactive profiles; exports are read-only and use exclusive creation or atomic confirmed replacement. The Bindings workflow edits an isolated draft, preserves invalid input as inline feedback without mutating the last valid snapshot, and saves only as a new inactive profile. The Windows executor maps validated clicks, held buttons, wheel steps, keys, and shortcuts to Win32 packets with partial-send cleanup. The application registers `Ctrl+Alt+Shift+F11` only after explicit consent and releases/unregisters on every safety transition. Guided calibration UI, statistical outlier rejection, mapping, smoothing, and gaze pointer output remain pending.

See:

- [`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) for the roadmap;
- [`DESIGN.md`](./DESIGN.md) for the native UI system;
- [`docs/TODO.md`](./docs/TODO.md) for the active checklist;
- [`docs/changelog/`](./docs/changelog/README.md) for dated implementation records.

## OpenAI Build Week 2026

- Recommended submission category: **Apps for Your Life**; the human entrant must confirm it.
- Target platform: Windows 10/11 x64, Python 3.11, and an ordinary webcam; live and visual QA is currently recorded on Windows 11 x64.
- Build-period evidence: Git history begins on July 19, 2026, inside the July 13-21 submission window and remains unsquashed.
- Runtime boundary: GPT-5.6 and Codex helped build MEYES; neither is an application runtime dependency and no OpenAI API key is required.
- Safety boundary: the application starts with OS input disconnected. Live Input is an explicit, volatile Windows opt-in and must be shown with its consent, emergency, and release behavior in any demo that uses real output.

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

1. Start the camera and verify stable gesture events in **Diagnostics**.
2. Open **Live Input** and read the displayed safety checklist.
3. Release physical mouse buttons and modifier keys, then type `ENABLE LIVE INPUT` exactly.
4. Select **Arm Live Input**. Confirm the persistent bar says `LIVE INPUT` before testing in a
   disposable target window.
5. Press `Ctrl+Alt+Shift+F11`, select **Return to Safe Mode**, pause/stop the camera, or close MEYES
   to gate dispatch and release all input owned by MEYES.

Consent is not persisted. A profile change also disarms Live Input and requires new consent.
Windows may block `SendInput` when the target process runs at a higher integrity level; MEYES
cannot bypass that operating-system boundary. Automated tests use fake native APIs and never send
real input.

## Verify

```powershell
.\scripts\check.ps1
```

The check script runs formatting verification, linting, type checking, and tests.

No webcam is required for the deterministic test suite. A webcam is required only for the live camera and model path.

No external sample dataset is required. Deterministic normalized observation fixtures are
included under `tests/fixtures/observation_sequences/`.

## Local data

Meyes uses Windows-appropriate per-user locations:

- configuration: `%APPDATA%\Meyes\config.json`;
- logs: `%LOCALAPPDATA%\Meyes\Logs\meyes.log`;
- calibration and other local data: `%LOCALAPPDATA%\Meyes\`.

MEYES does not intentionally persist or transmit camera frames. MediaPipe performs input-media processing on-device, while Google's current MediaPipe terms state that Solution APIs may periodically contact Google and send non-input usage, performance, application, and system metrics. See [PRIVACY.md](./PRIVACY.md) for the precise boundary.

## Design reference

The native design system uses the MIT-licensed [nutlope/hallmark](https://github.com/nutlope/hallmark) project as a review methodology and anti-generic design reference. No Hallmark code, generated page, screenshot, or asset is copied into MEYES; the application defines its own PySide6 information architecture and visual tokens.

## License and third-party components

Original MEYES code and documentation are licensed under the [MIT License](./LICENSE). Third-party libraries and model assets retain their upstream terms; their provenance, model-card licenses, and distribution notes are recorded in [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).
