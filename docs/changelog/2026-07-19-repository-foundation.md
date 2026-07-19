# 2026-07-19 — Repository foundation

## Summary

Implemented the runnable Phase 0 foundation on Python 3.11. The application now has a native PySide6 shell, safe local configuration, structured rotating logs, dependency locking, static checks, and automated tests.

## Added

- `pyproject.toml` with Python 3.11 constraints, runtime dependencies, development groups, and quality-tool configuration.
- `uv.lock` and a project-local `.venv` workflow.
- `src/meyes` application package and console entry point.
- Initial “calm control room” PySide6 shell with persistent tracking and safety status.
- Strict Pydantic configuration models for app, camera, tracking, UI, and privacy settings.
- Atomic JSON configuration persistence with timestamped recovery of malformed or invalid files.
- Windows-appropriate roaming config and local data/log paths.
- Structured JSON-lines logging with file rotation.
- PowerShell scripts for environment sync, running, testing, and full verification.
- Unit tests for configuration persistence/recovery, logging, and the main-window shell.
- Root README, changelog, and Python/tool cache exclusions.

## Changed

- Updated the active TODO checklist to reflect completed Phase 0 work.
- Documented the local development and verification workflow.

## Verification

Environment:

```text
Python 3.11.15
uv 0.11.29
PySide6 / Qt 6.11.1
```

Commands:

```powershell
python -m uv sync --group dev --python 3.11
python -m uv run ruff format --check .
python -m uv run ruff check .
python -m uv run mypy
$env:QT_QPA_PLATFORM='offscreen'; python -m uv run pytest
```

Results:

- Ruff formatting: passed, 15 files formatted.
- Ruff lint: passed.
- mypy strict: passed, 15 source files checked.
- pytest: 6 passed.

## Known limitations

- The dashboard is a static application shell; camera capture is not connected yet.
- The Resume button is deliberately disabled until camera lifecycle controls exist.
- No MediaPipe or Windows input backend is included.
- Visual QA currently covers the Qt shell smoke test; live camera layouts will require rendered/manual verification.

## Next task

Implement the camera domain and OpenCV capture worker with explicit lifecycle states, latest-frame-only buffering, measured FPS, and deterministic shutdown tests.
