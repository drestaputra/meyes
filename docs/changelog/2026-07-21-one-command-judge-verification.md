# 2026-07-21 - One-command judge verification

## Summary

Added a single safe PowerShell entry point that reproduces locked source setup, validates the
installed application entry point, and runs the complete deterministic gate.

## Safety boundary

- The script installs only the committed frozen dependency graph and development group.
- It imports the configured `meyes` entry point without calling it.
- It runs Ruff formatting, Ruff lint, strict mypy, and pytest.
- It never launches the application, opens a camera, constructs `SendInput`, or arms Live Input.

## Verification

- PowerShell parser validation passed.
- Frozen dependency sync completed against the committed lockfile.
- The installed `meyes` package and configured `meyes.__main__:main` entry point imported.
- Ruff formatting, Ruff lint, strict mypy, and all 740 tests passed on native Windows Qt.
- Submission preflight is rerun before and after push.
