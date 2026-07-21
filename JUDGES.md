# MEYES judge quickstart

MEYES is currently a Windows source build for local vision diagnostics. Its runtime requires
no OpenAI API key, paid service, OpenAI account, network-hosted demo, or sample dataset. A
webcam is needed for the live path; deterministic verification does not need one. The initial
Git checkout and dependency installation normally require network access, and a private
repository requires the judge's invited GitHub access.

Use the exact repository revision linked from Devpost. Commit `57e08f2` is the first explicit
GPT-5.6 implementation evidence baseline; later unsquashed commits add the complete calibration,
cursor-candidate, guarded persistence, and explicitly armed Windows pointer path.

The human recording operator has a separate safety and evidence checklist in
[`docs/DEMO_RUNBOOK.md`](./docs/DEMO_RUNBOOK.md); its completion is not asserted by this guide.

## Supported and tested path

- Target compatibility: Windows 10/11 x64.
- Recorded live/visual QA environment: Windows 11 Home Single Language x64, build 26200.
- Runtime: CPython 3.11 only.
- Dependency manager: [`uv`](https://docs.astral.sh/uv/), using the committed `uv.lock`.
- Live hardware: a conventional webcam available to OpenCV.
- Current delivery: source checkout only; no installer or packaged executable is claimed.
- Fresh-source evidence: commit `65b2e48` passed locked sync, entry-point import, Ruff, strict mypy,
  and 740 tests in an isolated environment on the same Windows 11 host. This is not a Windows 10 or
  second-machine claim.

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

For a one-command locked setup, entry-point smoke test, and deterministic quality gate, run:

```powershell
.\scripts\judge_verify.ps1
```

This verification command does not open a camera or arm operating-system input. Start the app
separately with `.\scripts\run_dev.ps1` when you are ready for the live evaluation path.

For a machine-readable installed-package check without importing Qt or opening hardware, run:

```powershell
uv run --frozen meyes --diagnose-install
```

## Live evaluation path

On a fresh configuration, review the three-step first-run orientation. It opens no camera and sends
no OS input; select Not now to leave it pending, or confirm the final Safe Mode dialog to record
completion locally.

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

Keyboard shell check: focus the left navigation and use Up/Down, or press Ctrl+1 through Ctrl+9 to
select the displayed page number. Direct shortcuts return focus to the navigation list and the
selection is persisted locally.

If the Windows session exposes a system tray, its MEYES menu mirrors current camera/Safe state and
offers Show, Pause/Resume, Return to Safe Mode, and Quit. Closing the main window still shuts down
workers and the tray icon rather than leaving a hidden background process.

High Contrast support is preference-driven: when Windows reports High Contrast enabled, MEYES
suppresses its custom palette so Qt uses system colors/focus. This host's automated native probe
reported High Contrast disabled; an actual enabled-theme human visual pass remains pending.

Optional controlled OS-output check on Windows:

1. Use a disposable target window and keep `Ctrl+Alt+Shift+F11` available.
2. With the camera running, open **Live Input**, release physical mouse/modifier inputs, select
   **Arm Live Input**, review the safety dialog, and confirm **Arm Live Input**.
3. Confirm the persistent status changes to `LIVE INPUT`. Default left/right winks issue left/right
   clicks and temple tap/hold gestures issue bounded scroll steps.
4. Press `Ctrl+Alt+Shift+F11` and confirm MEYES returns to `SAFE MODE`; camera pause/stop, profile
   change, and application close also disarm and release owned input.

Live Input consent is never persisted. Windows UIPI can block injection into a higher-integrity
target without a specific error; run MEYES and the disposable target at the same integrity level.

Optional calibration and gaze-pointer check:

1. Treat this as an advanced path. The default calibration acceptance limits are intentionally
   unset, so a fit reports `Review Required` and cannot move the pointer by default.
2. If the submitted revision includes a preconfigured, evidence-backed four-limit policy, complete
   all nine full-screen points and confirm the fit reports `Accepted`. Do not weaken limits merely
   to force a demo.
3. Confirm the saved-calibration status names the current physical display. If a saved envelope
   already exists, replacement requires a cancel-default modal confirmation and releases Live Input.
4. Re-arm Live Input through its per-session confirmation dialog; accepted fresh gaze candidates may now move the
   primary-screen pointer. Every movement revalidates current physical geometry.
5. Change no display setting while armed. A geometry mismatch or native failure removes the cursor
   pipeline, faults Live Input, releases owned input, and requests tracking pause.

The committed display evidence covers 100% scale only. Do not claim 125% or 150% verification, or
broad physical reach, until the corresponding human-controlled evidence is committed.

Profile transfer check:

1. Open **Profiles**, select **Default**, and export it to a temporary `.json` file.
2. Select **Browse**, choose that file, enter `Default Copy` as the optional local name, and import.
3. Confirm `Default Copy` appears selected but inactive, while the active profile and tracking state
   remain unchanged. Import never overwrites an existing local profile.
4. Delete the temporary exported file when finished. The import copy can be removed through the
   modal-confirmed, recoverable profile lifecycle control.

Lighting, camera field of view, occlusion, and landmark confidence affect live detection.
Do not interpret the diagnostics as a medical or safety assessment.

## Deterministic verification

```powershell
.\scripts\judge_verify.ps1
```

This performs a frozen dependency sync, verifies the configured package entry point, runs Ruff
format verification, Ruff lint, strict mypy, and pytest, then builds and checks an isolated wheel
install for the exact bundled model assets. Tests use fake camera and model backends plus normalized
observation sequences under
`tests/fixtures/observation_sequences/`; they do not activate a webcam, save frames, or send
operating-system input.

The script resolves `uv` or `python -m uv`, runs against the frozen lockfile, and does not force Qt's
offscreen backend on Windows. If neither uv route is installed, it stops with one prerequisite
message instead of continuing through multiple failed commands.

`.\scripts\profile_safe.ps1` separately measures the real local model adapters on a bounded
all-zero in-memory frame and prints limitation-labeled JSON. It activates no camera, GUI, hotkey, or
OS input and is not evidence of live accuracy or throughput. Exact clean-revision results are in
`docs/evidence/performance/2026-07-21.md`.

Maintainers can build an exact-revision wheel plus `BUILD-MANIFEST.json` and `SHA256SUMS.txt` with
`.\scripts\build_release.ps1`. The script requires clean live-remote parity and repeats this judge
gate. It records that code signing is not configured, marks Authenticode as not applicable to the
ZIP-based wheel, and preserves the raw Windows probe status. No standalone executable or installer
is claimed. The clean-revision artifact evidence is in
`docs/evidence/release/2026-07-21.md`.

## Expected current scope

Working in the submitted source build:

- camera discovery, start, pause/resume, stop, recovery, and aspect-correct preview;
- a dedicated capture-health/settings view with stopped-only, disarm-first updates synchronized to
  Dashboard without duplicating camera start controls;
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
  to `Review Required` because no benchmark limits are claimed, and activates only accepted fits;
- a configurable One Euro 2D filter with monotonic-time enforcement, velocity-adaptive cutoff,
  independent axes, and stale-gap reset in the accepted cursor-candidate pipeline;
- a Sensitivity view for validated One Euro and temple-gate values that releases Live Input before
  persistence and rebuilds only a still-active accepted calibration pipeline;
- a normalized-to-physical-pixel primary-screen mapper with inclusive bounds, explicit clamping
  evidence, signed 32-bit validation, and no executor dependency;
- a cursor movement gate that starts suspended, handles overlapping temple holds and tap
  pulses, applies a configurable resume delay, and never overrides tracking-loss suspension;
- a proof-carrying accepted-calibration token and executor-independent pipeline that emits candidates
  only through open freshness/gate boundaries and has no `InputExecutor` dependency;
- Qt-owned cursor diagnostics wired to gaze, gesture, camera lifecycle, and freshness signals;
- armed-only delivery of accepted, display-matched candidates to primary-monitor absolute
  `SendInput`, with per-movement display-provenance revalidation and mismatch/native failure
  removing the pipeline, gating output, releasing owned input, and requesting tracking pause;
- a read-only Windows evidence probe recording native geometry, system DPI, Qt logical geometry,
  device-pixel ratio, and consistency checks; the committed 100% row passes, while 125% and 150%
  are explicitly pending;
- modal-confirmed replacement of an existing saved calibration, retaining the prior envelope and
  using the accepted fit only as volatile provisioning until confirmation releases Live Input;
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
- inactive-only profile rename, modal-confirmed restore-from-Default and deletion that
  retains a local recovery backup without changing the runtime snapshot;
- bounded, duplicate-key-rejecting profile JSON import as a new inactive snapshot, plus read-only
  export with explicit collision handling and atomic confirmed replacement;
- a Qt-owned fake runtime dispatcher with held-input cleanup, no-catch-up deadline polling,
  fault recovery, and a bounded simulated primitive trace in Diagnostics;
- an application-wired Windows `SendInput` executor with owned-state tracking, partial-send
  containment, and reverse-order cleanup;
- a volatile Live Input session requiring cancel-default modal consent, successful
  `Ctrl+Alt+Shift+F11` registration, clear physical inputs, and release-first arming;
- emergency, camera-lifecycle, profile-transition, executor-fault, page-close, and application-close
  disarm/release paths, with a persistent non-color status boundary;
- watchdog-driven expiry and native diagnostics that start with OS input disconnected;
- deterministic shutdown and race/lifecycle regression coverage.

Intentionally not implemented or not enabled:

- evidence-backed default calibration limits and broad physical-device reach validation;
- bulk calibration-backup cleanup, a standalone Windows executable, or an installer;
- native 125%/150% display-scale and enabled High Contrast human evidence.

The README, video, and Devpost description should be judged against this boundary and any
later capabilities present in the exact linked commit, not against roadmap copy.
The consolidated pass/partial/blocked matrix is in `MVP_ACCEPTANCE.md`; it explicitly does not claim
a standalone MVP release or completed Devpost submission.

## Local files and troubleshooting

- Configuration: `%APPDATA%\Meyes\config.json`
- Rotating JSON-lines logs: `%LOCALAPPDATA%\Meyes\Logs\meyes.log`
- Model provenance and checksums: `resources/models/README.md`
- Privacy boundary: `PRIVACY.md`
- Safe recovery guide: `TROUBLESHOOTING.md`
- Future Windows signing requirements: `SIGNING.md`
- Third-party rights: `THIRD_PARTY_NOTICES.md`

If no camera appears, grant Windows camera permission, close other applications that may
hold the camera, then select **Refresh**. If a model cannot initialize, run the deterministic
checks to verify the bundled files and include the local log when reporting the failure. No
credentials are required.

If the repository remains private, judge access must be granted to both
`testing@devpost.com` and `build-week-event@openai.com` before the deadline. This is an
external submission step and is not asserted complete here.
