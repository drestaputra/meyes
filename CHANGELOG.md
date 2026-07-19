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
