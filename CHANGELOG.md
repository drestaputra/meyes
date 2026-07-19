# Changelog

All notable changes to MEYES will be documented in this file. Detailed implementation notes are stored in [`docs/changelog/`](./docs/changelog/README.md).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project intends to use semantic versioning once distributable builds begin.

## [Unreleased]

### Added

- Initial Python 3.11 project configuration using `uv`.
- PySide6 application shell following the MEYES design baseline.
- Typed Pydantic configuration with atomic persistence and corrupt-file recovery.
- Structured JSON rotating-file logging.
- Ruff, mypy, pytest, and PowerShell development workflows.
- OpenCV camera backend and bounded device enumeration.
- Thread-safe latest-frame-only buffer and rolling FPS measurement.
- Validated camera lifecycle state machine with pause, recovery, and deterministic shutdown.
- Webcam-free camera worker tests, including blocked-read shutdown recovery.
- Responsive camera dashboard with asynchronous discovery and device selection.
- Preview-only mirroring that leaves processing coordinates unchanged.
- Start, pause, resume, and stop controls with textual camera health and FPS.
- Camera preference persistence and clean window-close shutdown.
- Native Windows visual QA and physical webcam/controller smoke tests.
- Official local MediaPipe Face Landmarker asset with recorded SHA-256 integrity.
- Framework-independent face observations with independent eye openness and iris centers.
- Latest-frame face inference worker with health, FPS, latency, and shutdown reporting.
- Semantic gesture event domain and central gesture engine.
- Hysteretic left/right wink state machine with both-eye blink suppression.
- Configurable minimum/maximum duration, cooldown, synchronization window, and tracking timeout.
- Recorded normalized observation fixtures for deterministic gesture regression tests.
