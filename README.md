# Meyes

Meyes is a Windows desktop application that lets users control the mouse using eye gaze and configurable facial or hand gestures.

Default controls:

- gaze moves the pointer;
- left wink performs left click;
- right wink performs right click;
- right-temple gesture scrolls up;
- left-temple gesture scrolls down.

Every gesture can be rebound to supported mouse or keyboard actions. Camera processing runs locally on the device.

> Status: early development. Meyes is not a medical device and should not be relied upon for safety-critical operation.

## Development status

Phase 0 and Phase 1 are complete. The runnable application provides local configuration recovery, structured rotating logs, a PySide6 camera dashboard, asynchronous device discovery, mirrored preview, lifecycle controls, health/FPS indicators, settings persistence, and tested shutdown/recovery behavior. MediaPipe is intentionally deferred until Phase 2.

See:

- [`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) for the roadmap;
- [`DESIGN.md`](./DESIGN.md) for the native UI system;
- [`docs/TODO.md`](./docs/TODO.md) for the active checklist;
- [`docs/changelog/`](./docs/changelog/README.md) for dated implementation records.

## Requirements

- Windows 10 or Windows 11, 64-bit;
- Python 3.11;
- [`uv`](https://docs.astral.sh/uv/).

## Setup

```powershell
uv python install 3.11
uv sync --group dev
```

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

## Local data

Meyes uses Windows-appropriate per-user locations:

- configuration: `%APPDATA%\Meyes\config.json`;
- logs: `%LOCALAPPDATA%\Meyes\Logs\meyes.log`;
- calibration and other local data: `%LOCALAPPDATA%\Meyes\`.

Camera frames are not stored or transmitted by default.
