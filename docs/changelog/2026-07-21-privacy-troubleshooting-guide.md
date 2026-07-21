# 2026-07-21 - Privacy and troubleshooting guide

## Summary

Completed a source-build troubleshooting guide that keeps Safe Mode and the existing native input
gates intact. Linked recovery guidance to the already detailed privacy/data-lifecycle boundary.

## Included guidance

- Non-capturing first checks and installed-model diagnostics.
- A dedicated diagnostic PowerShell entry point that uses the repository's direct-uv or
  `python -m uv` fallback and frozen environment.
- Symptom-specific setup, camera, model, calibration, display-provenance, Live Input, settings, and
  High Contrast recovery.
- Reversible local-file handling that prefers guarded application controls and never treats direct
  envelope editing as recovery.
- Deterministic judge verification and exact limits of what automation can prove.
- A privacy-aware issue-report checklist with explicit redaction/capture cautions.

## Verification

- Checked repository links and commands against the current README, CLI, scripts, privacy document,
  and guarded UI behavior.
- Ran the local submission preflight in development mode.
- No camera, model inference, file deletion, or operating-system input was activated.
