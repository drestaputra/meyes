# MEYES judge quickstart

MEYES is currently a Windows source build for local vision diagnostics. Its runtime requires
no OpenAI API key, paid service, OpenAI account, network-hosted demo, or sample dataset. A
webcam is needed for the live path; deterministic verification does not need one. The initial
Git checkout and dependency installation normally require network access, and a private
repository requires the judge's invited GitHub access.

Use the exact repository revision linked from Devpost. Commit `57e08f2` is the first explicit
GPT-5.6 implementation evidence baseline; later commits add submission readiness and further
gesture work.

## Supported and tested path

- Target compatibility: Windows 10/11 x64.
- Recorded live/visual QA environment: Windows 11 Home Single Language x64, build 26200.
- Runtime: CPython 3.11 only.
- Dependency manager: [`uv`](https://docs.astral.sh/uv/), using the committed `uv.lock`.
- Live hardware: a conventional webcam available to OpenCV.
- Current delivery: source checkout only; no installer or packaged executable is claimed.

## Source quickstart

From PowerShell in the repository root:

```powershell
uv python install 3.11
uv sync --frozen --group dev
uv run meyes
```

Install `uv` from the linked official instructions before running these commands. If `uv` is
installed as a Python module but its launcher is not on `PATH`, replace each `uv` invocation
with `python -m uv`.

The official MediaPipe face and hand task bundles are already included and checksum-tested,
so no model download is needed. Windows may ask for camera permission on first use.

## Live evaluation path

1. Open **Dashboard**.
2. Select **Refresh** to enumerate cameras.
3. Choose a camera and select **Start camera**.
4. Confirm the preview is live and camera health/FPS are updating.
5. Open **Diagnostics**.
6. With a face visible, confirm face health, left/right eye openness, and inference latency
   update. A deliberate single-eye wink should add a semantic wink event. Synchronized
   both-eye closure is designed to suppress ordinary blink events, subject to live tracking
   quality.
7. Bring an index fingertip toward the same-side temple while keeping the face visible.
   Confirm hand health/count and the left/right normalized temple-distance diagnostics update.
   After a stable approach, the matching state can become **Near**; a stable release becomes
   **Far**, and tracking loss eventually becomes **Unknown**. A short confirmed release can
   add a `*_TEMPLE_TAP` event; a sustained Near state adds one `*_TEMPLE_HOLD_START`, followed
   by `*_TEMPLE_HOLD_END` on release or tracking loss, subject to live tracking quality.
8. Pause or stop the camera and confirm live observations clear. Close the window and confirm
   the application exits without a hanging worker.

Optional controlled OS-output check on Windows:

1. Use a disposable target window and keep `Ctrl+Alt+Shift+F11` available.
2. With the camera running, open **Live Input**, release physical mouse/modifier inputs, type
   `ENABLE LIVE INPUT` exactly, and select **Arm Live Input**.
3. Confirm the persistent status changes to `LIVE INPUT`. Default left/right winks issue left/right
   clicks and temple tap/hold gestures issue bounded scroll steps.
4. Press `Ctrl+Alt+Shift+F11` and confirm MEYES returns to `SAFE MODE`; camera pause/stop, profile
   change, and application close also disarm and release owned input.

Live Input consent is never persisted. Windows UIPI can block injection into a higher-integrity
target without a specific error; run MEYES and the disposable target at the same integrity level.

Profile transfer check:

1. Open **Profiles**, select **Default**, and export it to a temporary `.json` file.
2. Select **Browse**, choose that file, enter `Default Copy` as the optional local name, and import.
3. Confirm `Default Copy` appears selected but inactive, while the active profile and tracking state
   remain unchanged. Import never overwrites an existing local profile.
4. Delete the temporary exported file when finished. The import copy can be removed through the
   exact-name-confirmed, recoverable profile lifecycle control.

Lighting, camera field of view, occlusion, and landmark confidence affect live detection.
Do not interpret the diagnostics as a medical or safety assessment.

## Deterministic verification

```powershell
.\scripts\check.ps1
```

This runs Ruff format verification, Ruff lint, strict mypy, and pytest. Tests use fake camera
and model backends plus normalized observation sequences under
`tests/fixtures/observation_sequences/`; they do not activate a webcam, save frames, or send
operating-system input.

## Expected current scope

Working in the submitted source build:

- camera discovery, start, pause/resume, stop, recovery, and aspect-correct preview;
- independent local face and lower-cadence hand inference;
- fail-closed binocular iris-to-eye feature extraction with freshness expiry and explicit native
  Diagnostics status; these uncalibrated values are not screen coordinates;
- a distraction-free primary-display nine-point collector with targets at normalized 10/50/90%
  positions, Space/Enter/R/Escape controls, explicit capture, progress, retry, cancellation, quota,
  attempt, ordering, replay, range, binocular-consistency, and robust per-target median/MAD guards;
- a user-triggered volatile quadratic calibration fit after complete collection, with
  complete-target coverage, matrix-rank, conditioning, finite-output, deterministic per-target
  holdout-validation guards, visible metrics, and recoverable failure feedback;
- an optional all-or-none acceptance policy that reports every missed configured limit, defaults
  to `Review Required` because no benchmark limits are claimed, and never activates its mapper;
- a dormant configurable One Euro 2D filter with monotonic-time enforcement, velocity-adaptive
  cutoff, independent axes, and stale-gap reset, with no pointer-output consumer;
- a dormant normalized-to-physical-pixel primary-screen mapper with inclusive bounds, explicit
  clamping evidence, signed 32-bit validation, and no executor dependency;
- a dormant cursor movement gate that starts suspended, handles overlapping temple holds and tap
  pulses, applies a configurable resume delay, and never overrides tracking-loss suspension;
- a proof-carrying accepted-calibration token and fake-only pipeline that emits pixel candidates
  only through open freshness/gate boundaries and has no `InputExecutor` dependency;
- Qt-owned fake cursor diagnostics wired to gaze, gesture, camera lifecycle, and freshness signals,
  defaulting honestly to unavailable in production and never sending its candidate to the OS;
- normalized observations and left/right wink events with blink suppression;
- fresh face/hand pairing and scale-normalized fingertip-to-temple distances;
- independently stabilized Near/Far/Unknown temple states with ordering and timeout guards;
- independent semantic temple tap, hold-start, and hold-end events with cooldown and
  lifecycle-safe hold termination;
- validated action schemas, logical default bindings, and a fail-closed user profile repository;
- a user-facing profile catalog that creates complete all-disabled profiles, activates a
  selected snapshot through a pause-first transition, and previews all six simulated bindings;
- a no-JSON Bindings editor for every validated MVP action, with hold-only choice filtering,
  inline errors, isolated preview, dirty-draft preservation, and inactive save-as-copy;
- inactive-only profile rename, restore-from-Default, and exact-name-confirmed deletion that
  retains a local recovery backup without changing the runtime snapshot;
- bounded, duplicate-key-rejecting profile JSON import as a new inactive snapshot, plus read-only
  export with explicit collision handling and atomic confirmed replacement;
- a Qt-owned fake runtime dispatcher with held-input cleanup, no-catch-up deadline polling,
  fault recovery, and a bounded simulated primitive trace in Diagnostics;
- an application-wired Windows `SendInput` executor with owned-state tracking, partial-send
  containment, and reverse-order cleanup;
- a volatile Live Input session requiring exact typed consent, successful
  `Ctrl+Alt+Shift+F11` registration, clear physical inputs, and release-first arming;
- emergency, camera-lifecycle, profile-transition, executor-fault, page-close, and application-close
  disarm/release paths, with a persistent non-color status boundary;
- watchdog-driven expiry and native diagnostics that start with OS input disconnected;
- deterministic shutdown and race/lifecycle regression coverage.

Intentionally not implemented or not enabled:

- evidence-backed default calibration limits, mapper persistence/activation, and cursor mapping;
- tray controls, gaze pointer movement, or an installer.

The README, video, and Devpost description should be judged against this boundary and any
later capabilities present in the exact linked commit, not against roadmap copy.

## Local files and troubleshooting

- Configuration: `%APPDATA%\Meyes\config.json`
- Rotating JSON-lines logs: `%LOCALAPPDATA%\Meyes\Logs\meyes.log`
- Model provenance and checksums: `resources/models/README.md`
- Privacy boundary: `PRIVACY.md`
- Third-party rights: `THIRD_PARTY_NOTICES.md`

If no camera appears, grant Windows camera permission, close other applications that may
hold the camera, then select **Refresh**. If a model cannot initialize, run the deterministic
checks to verify the bundled files and include the local log when reporting the failure. No
credentials are required.

If the repository remains private, judge access must be granted to both
`testing@devpost.com` and `build-week-event@openai.com` before the deadline. This is an
external submission step and is not asserted complete here.
