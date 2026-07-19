# MEYES

MEYES is a Windows-first local vision application exploring hands-free computer interaction with an ordinary webcam. The current OpenAI Build Week build runs independent face and hand landmark pipelines, detects left/right wink events, calculates same-side fingertip-to-temple distance, and exposes those signals in Safe Mode diagnostics. It does **not** send mouse or keyboard input yet.

The planned product controls are gaze-driven pointer movement, wink clicks, and temple-gesture scrolling with configurable bindings. Those mappings are roadmap items, not claims about the current runnable build.

> Status: early development. Meyes is not a medical device and should not be relied upon for safety-critical operation.

## Development status

Phase 0, Phase 1, and Phase 2 are complete. Phase 3 is in progress with local face and lower-cadence hand inference composed into Qt-safe diagnostics, live aspect-correct temple-distance features, and watchdog-driven freshness expiry. Operating-system input remains intentionally disabled while temple gesture semantics are developed.

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
- Safety boundary: the submitted scope is local vision and diagnostics only until the README, demo, and code all truthfully show otherwise.

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
uv sync --group dev
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
