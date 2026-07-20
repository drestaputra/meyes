# MEYES privacy and safety boundary

This document describes the current source build. MEYES is a local vision and hands-free input
application and is not a medical device. It starts in Safe Mode with operating-system input
disconnected; on Windows, a user may explicitly arm configured mouse and keyboard actions for the
current session.

## Data handling

| Data | Current handling |
|---|---|
| Webcam frames | Held in bounded, latest-only memory for preview and local inference, then discarded. MEYES does not intentionally save or upload frames. |
| Face and hand landmarks | Derived locally and held in memory for diagnostics and gesture state. They are not written as images or recordings. |
| Gaze features | Binocular iris-to-eye ratios are derived locally, held only in memory, and cleared on tracking suspension or freshness timeout. They are not calibrated screen coordinates and are not persisted in this build. |
| Calibration samples | Raw target/feature pairs remain only in bounded session memory. Escape, closing the full-screen presentation, navigation away, tracking loss, Live Input arming, cancellation, restart, and shutdown discard them. Raw samples are not included in the accepted-calibration envelope. |
| Accepted calibration envelope | When a newly fitted mapper passes every configured limit, MEYES atomically stores only its quadratic coefficients, holdout metrics, exact accepting policy, UTC creation time, physical primary-screen rectangle, schema version, and a corruption-detection SHA-256 checksum in `%LOCALAPPDATA%\Meyes\accepted-calibration.json`. It is recovered once at startup only under the identical current policy and display geometry. Invalid files are never activated and may be renamed to timestamped `.invalid-*.json` backups. Legacy schema-1 files are preserved but not recovered. The checksum is not authentication against a local attacker. |
| Calibration acceptance limits | Optional numeric evidence limits are local configuration values. All four default to unset, so a mapper remains `Review Required`; persistence recovery also remains disabled without a complete policy. |
| Cursor smoothing settings | One Euro cutoff, speed coefficient, derivative cutoff, and stale-gap values are local configuration consumed only by the accepted fake diagnostics pipeline. They do not enable or move the pointer. |
| Cursor gate settings | Temple-freeze and resume-delay values are local configuration consumed by fake diagnostics. Disabling temple freeze never disables tracking-loss suspension, and the gate has no pointer executor. |
| Fake cursor diagnostics | Production constructs a no-executor candidate pipeline only after volatile policy acceptance plus a validated physical-screen read. The latest normalized and physical-pixel candidate is held only in memory and removed on block, expiry, suspension, acceptance loss, or fault. It is never persisted. |
| Gesture diagnostics | Displayed in memory. Conservative semantic event metadata may appear in the local application log; frames and landmark arrays are not intentionally logged. |
| Configuration | Stored in `%APPDATA%\Meyes\config.json`. A corrupt configuration may be renamed to a timestamped backup in the same directory before defaults are restored. |
| Logs | Stored as rotating JSON lines in `%LOCALAPPDATA%\Meyes\Logs\meyes.log`, limited to 2 MiB per file with three backups. Logs contain timestamps, severity/category, lifecycle and error details, camera settings, and semantic event metadata. |
| Model assets | Loaded from the repository's `resources/models/` directory and verified by size and SHA-256 in tests. |
| Live Input consent | Held only in widget memory long enough to validate the exact phrase, then cleared. It is not persisted or intentionally logged. |
| Profile import/export | Reads or writes only the local `.json` path explicitly selected in the native file dialog. Imports are copied into the local profile catalog; exports are not uploaded or transmitted by MEYES. |

`diagnostic_recording_enabled` defaults to `false`, and the current build has no frame
recording implementation or recording UI. Enabling that configuration field does not create
a recording pipeline.

Accepted-calibration recovery is isolated from Live Input. It can configure only the fake cursor
diagnostics pipeline; it never restores the exact consent phrase, registers an emergency hotkey,
constructs `SendInput`, or changes the startup SAFE state.

## MediaPipe network boundary

MEYES loads the included MediaPipe task files from local disk and does not implement a frame
upload path. Google's current [MediaPipe Solution API Terms of
Service](https://developers.google.com/edge/mediapipe/legal/tos) state that input media is
processed on-device and is not sent to Google servers. The same terms state that Solution
APIs may periodically contact Google for bug fixes, updated models, and hardware accelerator
compatibility information, and may send non-input usage, performance, application, and
system metrics.

Accordingly, “local processing” does not mean that every dependency is guaranteed to make
zero network requests. Use an operating-system firewall or an audited offline environment if
that distinction is important to the evaluation.

## OpenAI boundary

Codex and GPT-5.6 were development tools used to build this project. They are not a MEYES
runtime dependency. The application contains no OpenAI API call, requires no API key, and
does not send camera frames to Codex or GPT-5.6 through its runtime.

## User control and deletion

- Camera processing begins only after **Start camera** is selected.
- Pause, stop, or application close ends the live pipeline and clears current observations.
- Real OS output requires exact per-session consent and a running camera. Emergency shortcut,
  disarm, camera pause/stop/fault, profile change, or application close gates output and attempts
  to release all mouse/keyboard state owned by MEYES.
- Delete `config.json` and any timestamped corrupt-config backups from `%APPDATA%\Meyes\`
  to remove saved preferences.
- Delete `meyes.log` and its numbered backups from `%LOCALAPPDATA%\Meyes\Logs\` to remove
  local logs. Close MEYES first so the files are not in use.
- Delete `accepted-calibration.json` and any `accepted-calibration.invalid-*.json` backups from
  `%LOCALAPPDATA%\Meyes\` to remove stored mapper coefficients and validation evidence.

MEYES does not currently provide an in-app deletion control, cloud account, telemetry opt-out
for MediaPipe, or automated data-retention scheduler.

## Responsible capture and demo use

Only point the camera at people who know they are being captured and displayed in the camera
view. Before publishing a demo,
review the full frame for bystanders, private screens, names, notifications, addresses, and
other identifying information. Obtain permission for every identifiable person, voice,
image, mark, and media asset included in the submission.
