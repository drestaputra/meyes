# MEYES troubleshooting

This guide covers the current Windows source build and Python wheel. MEYES is not a medical or
safety device. Recovery should preserve Safe Mode: do not bypass consent, calibration provenance,
the emergency shortcut, physical-input checks, or display-geometry validation.

## First safe checks

1. If operating-system input is active or behaving unexpectedly, press `Ctrl+Alt+Shift+F11`, use
   **Return to Safe Mode**, stop the camera, or close MEYES.
2. Keep the camera stopped while changing camera settings or investigating another application that
   may own the device.
3. Run the non-capturing installation diagnostic:

   ```powershell
   .\scripts\diagnose_install.ps1
   ```

   This checks the supported Python/platform boundary and exact bundled model size/checksum without
   importing Qt, opening a camera, running model inference, or arming OS input.
4. Review the newest JSON-lines records in `%LOCALAPPDATA%\Meyes\Logs\meyes.log`. Remove personal
   paths or machine details before sharing a log.

## Symptom guide

| Symptom | Safe checks and recovery |
|---|---|
| Setup rejects Python | MEYES currently requires CPython `>=3.11,<3.12`. Install Python 3.11 and uv, then run `.\scripts\sync.ps1`. Do not remove the frozen-lock requirement to hide a dependency mismatch. |
| Application does not open | Run `.\scripts\diagnose_install.ps1`, then `.\scripts\run_dev.ps1`. Check the terminal and local log for the first error. The wheel is not a standalone executable or installer. |
| Model integrity check fails | Do not download an unverified replacement into the package. Reinstall or rebuild from the exact repository revision, then rerun the diagnostic. Expected model provenance and hashes are in `resources/models/README.md`. |
| No camera is listed | Grant desktop camera access in Windows privacy settings, close applications that may hold the camera, reconnect the device, and select **Refresh**. Keep MEYES stopped before changing its requested camera settings. |
| Camera opens but frames fail or stop | Select **Stop camera**, close competing capture software, reconnect the device, and retry. If the selected resolution/FPS is unsupported, stage a conservative setting in **Camera** while stopped. Preserve the log if recovery repeatedly fails. |
| Preview works but face/hand health is unavailable | Use even front lighting, keep the full face visible, avoid heavy occlusion, and keep the intended hand within frame. Check Diagnostics for worker health and freshness before retrying; never treat landmark output as a medical assessment. |
| Calibration remains `Review Required` | This is the safe default while all four evidence-backed acceptance limits are unset. Retry only if collection quality was poor. Do not invent thresholds or edit an envelope to force acceptance. |
| Saved calibration is not restored | Verify the configured acceptance policy and physical primary-display geometry are unchanged. A checksum, policy, or geometry mismatch intentionally prevents provisioning. Use the guarded Calibration recovery controls; never copy coefficients into a new envelope manually. |
| Cursor Diagnostics says unavailable | An accepted, current-policy, exact-display calibration is required. Recalibrate after display resolution, scaling, primary-monitor, or desktop topology changes. This state does not prevent Safe Mode gesture diagnostics. |
| Live Input will not arm | Confirm Windows, a running camera, the exact consent phrase, successful emergency-hotkey registration, and that physical mouse buttons plus Ctrl/Alt/Shift/Windows keys are released. Another application may own the emergency chord. A failed preflight must remain closed. |
| Live Input faults or disarms | Read the visible status and log before retrying. Camera lifecycle changes, profile changes, calibration/file-dialog entry, display mismatch, native output failure, and emergency activation deliberately release owned input and require fresh per-session consent. |
| Settings are rejected | Correct the inline validation error. Camera changes require capture to be stopped; Sensitivity and Camera saves first return Live Input to a safe released state. If that release fails, the previous runtime/configuration is intentionally retained. |
| UI colors look different in High Contrast | MEYES intentionally removes its custom stylesheet when Windows reports High Contrast enabled and defers colors/focus to the system theme. Safety state remains textual. An actual enabled-theme human QA pass is still pending. |

## Local-file recovery

Close MEYES before moving local files so no writer is active.

- Configuration: `%APPDATA%\Meyes\config.json`. Invalid configuration is automatically preserved as
  a timestamped backup before safe defaults are loaded. For a reversible manual reset, move the
  closed application's file to a user-chosen backup location instead of deleting it.
- Logs: `%LOCALAPPDATA%\Meyes\Logs\meyes.log` with rotating numbered backups. Removing logs is
  optional and does not reset application state.
- Accepted calibration: `%LOCALAPPDATA%\Meyes\accepted-calibration.json`. Prefer the guarded
  **Forget**, **Restore**, and exact-confirmation permanent-backup controls on Calibration. Raw edits
  invalidate the checksum and cannot restore Live Input consent.
- Profiles: use the in-app import/export and recoverable deletion controls. Imported profiles remain
  inactive until separately activated through the release-first transition.

The complete data lifecycle and deletion boundary is in [PRIVACY.md](./PRIVACY.md).

## Deterministic verification

For a source checkout, run:

```powershell
.\scripts\judge_verify.ps1
```

It performs frozen dependency synchronization, package entry-point verification, Ruff formatting
and lint checks, strict mypy, all unit tests, and an isolated installed-wheel verification. It does
not activate a webcam or OS input.

For release maintainers, `.\scripts\submission_preflight.ps1 -VerifyRemote` additionally checks
the exact live remote revision and submission invariants. It cannot verify camera hardware,
repository visibility to judges, video availability, entrant attestations, `/feedback`, or Devpost's
final submitted state.

## Reporting a reproducible issue

Include:

- the exact `git rev-parse HEAD` value or wheel filename and SHA-256;
- Windows version, Python version, and the redacted `--diagnose-install` JSON;
- the visible MEYES page/state and Safe versus Armed status;
- minimal reproduction steps and the first relevant redacted log record;
- whether a camera, calibration, High Contrast, display scaling, or real Live Input was involved.

Do not attach camera frames, faces, names, private screen content, a complete unreviewed log, or
local profile/calibration files unless every affected person has consented and the data is necessary.
