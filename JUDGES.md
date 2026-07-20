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
- normalized observations and left/right wink events with blink suppression;
- fresh face/hand pairing and scale-normalized fingertip-to-temple distances;
- independently stabilized Near/Far/Unknown temple states with ordering and timeout guards;
- independent semantic temple tap, hold-start, and hold-end events with cooldown and
  lifecycle-safe hold termination;
- validated action schemas, logical default bindings, a fail-closed user profile repository,
  and a runtime-disconnected fake-only dispatcher with held-input cleanup and fault recovery;
- watchdog-driven expiry and native Safe Mode diagnostics;
- deterministic shutdown and race/lifecycle regression coverage.

Intentionally not implemented or not enabled:

- mouse, keyboard, click, or scroll output;
- gaze calibration and cursor mapping;
- runtime binding execution, user-facing profile controls, global shortcuts, tray controls,
  or an installer.

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
