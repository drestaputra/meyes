# 2026-07-19 — Camera core

## Summary

Implemented the testable Phase 1 camera core without coupling it to Qt widgets. The camera layer now supports bounded device enumeration, OpenCV capture, explicit lifecycle transitions, latest-frame-only delivery, effective FPS measurement, pause/resume, reconnect attempts, and deterministic shutdown behavior.

## Added

- Camera domain models for devices, options, frames, health, and lifecycle status.
- Backend and capture protocols so worker tests do not require OpenCV or a webcam.
- OpenCV backend with Windows DirectShow capture and requested resolution/FPS configuration.
- Thread-safe latest-frame buffer that overwrites stale frames instead of queueing them.
- Rolling monotonic-timestamp FPS meter.
- Validated camera lifecycle state machine.
- Background camera worker with:
  - start, pause, resume, and stop operations;
  - camera-open and frame-read recovery;
  - health callbacks;
  - bounded retry delay;
  - capture release to unblock shutdown;
  - final frame clearing.
- Unit tests for buffering, FPS, valid/invalid state transitions, frame publication, open failure recovery, pause/resume, and blocked-read shutdown.

## Changed

- Added NumPy and OpenCV as runtime dependencies.
- Updated README, root changelog, and Phase 1 TODO progress.

## Verification

Commands:

```powershell
python -m uv run ruff format --check .
python -m uv run ruff check .
python -m uv run mypy
$env:QT_QPA_PLATFORM='offscreen'; python -m uv run pytest
```

Results:

- Ruff formatting: passed, 27 files checked.
- Ruff lint: passed.
- mypy strict: passed, 27 source files checked.
- pytest: 16 passed.

## Known limitations

- Camera enumeration currently uses bounded OpenCV index probing and generic device names.
- The camera core is not connected to Qt signals or dashboard controls yet.
- Preview mirroring, preview FPS, and rendered health states remain for the next iteration.
- A physical-camera smoke test has not yet been run.

## Next task

Connect the camera worker to a Qt controller and dashboard with device selection, mirrored preview, start/pause/resume/stop controls, textual health, capture/preview FPS, settings persistence, and clean window-close shutdown.
