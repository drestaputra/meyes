# 2026-07-20 - Bounded calibration sample collector

## Summary

Added the dormant domain state machine for gathering gaze features at nine ordered calibration
targets. The collector is bounded, volatile, deterministic, and independent of Qt, persistence,
mapping, smoothing, and operating-system input.

## Added

- Stable row-major target order from top-left through bottom-right at normalized 0.1/0.5/0.9
  target coordinates.
- Explicit idle, awaiting-target, collecting, target-complete, target-failed, complete, and
  cancelled states.
- Configurable per-target sample quota and attempt cap with strict upper bounds.
- Immutable progress snapshots, capture results, and accepted target/feature samples.
- Retry semantics that discard partial samples only for the failed current target.
- Cancel, reset, and restart paths that erase every volatile sample.

## Quality and safety decisions

- Collection must be explicitly armed for one target; gaze features offered at any other state are
  ignored without consuming attempts.
- Unavailable features, invalid metadata, duplicate/out-of-order frames, non-increasing timestamps,
  non-finite/out-of-range values, excessive inter-eye disagreement, and inconsistent combined
  values are rejected.
- Every offered frame while collecting consumes at most one bounded attempt, preventing an
  unbounded session during poor tracking.
- Out-of-range and rejected frames cannot be replayed later as corrected samples with the same
  sequence/timestamp.
- No camera, Qt view, calibration fit, saved artifact, cursor map, or `SendInput` path is connected.

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes\calibration tests\unit\test_calibration_session.py
.\.venv\Scripts\python.exe -m mypy src\meyes\calibration tests\unit\test_calibration_session.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_calibration_session.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 22 passed in 0.18 seconds.

Full repository gate:

- Ruff format: 108 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 108 source files.
- Pytest: 566 passed in 16.33 seconds.

## Known limitations

- The Calibration navigation entry remains a placeholder; this collector is not yet user-facing.
- Range and binocular-consistency gates are basic sample-quality checks, not statistical outlier
  rejection across a target population.
- The collector does not fit, validate, persist, or score a gaze-to-screen mapping.

## Next task

Connect the collector to a safe, cancellable Calibration page that consumes serialized gaze
features while keeping Live Input disarmed and makes no pointer-output claim.
