# 2026-07-22 - Smooth Pursuit live calibration

## Summary

Replaced the manually advanced nine-point collector with an automatic Smooth Pursuit workflow.
After a hands-free countdown, one target follows a cosine-eased serpentine path through all nine
broad screen regions while MEYES continuously pairs eye features with the target position at the
camera frame's capture timestamp.

The interaction follows the moving-target calibration approach described by
[Pfeuffer et al. (UIST 2013)](https://www.collaborative-ai.org/publications/pfeuffer13_uist/) and
retains the existing local-only, explicit-acceptance, and Live Input safety boundaries.

## Added

- A deterministic, bounded Smooth Pursuit trajectory with initial/final holds and eight eased legs.
- Exact continuous screen coordinates on live calibration samples while retaining stable nine-region
  labels for coverage, holdout stratification, and compatibility.
- Capture-time target synchronization using the same monotonic clock domain as camera frames.
- Horizontal and vertical target-following correlation evidence with live acquiring, following, and
  weak-following feedback.
- Automatic countdown, continuous progress, spatial coverage, rejected-frame count, informative
  failure result, and hands-free retry behavior.
- Tests for trajectory geometry, synchronized coordinates, coverage failure, non-following failure,
  retry/cancellation, continuous mapper targets, and full Qt orchestration.

## Changed

- Calibration now begins automatically after the full-screen countdown; Space, Enter, per-point
  capture, and per-point advance controls were removed.
- Quadratic fitting consumes the exact live target coordinates and applies deterministic Huber-style
  residual reweighting to reduce the effect of isolated camera noise.
- The in-shell Calibration page, onboarding copy, README, plan, demo runbook, Devpost draft, and
  submission evidence now describe the implemented Smooth Pursuit workflow.
- The existing saved-calibration envelope remains compatible because persisted output is still the
  same six-coefficient-per-axis polynomial mapper plus validation evidence.

## Safety and privacy

- Live Input is still released before calibration and is never armed by camera startup, countdown,
  capture, fitting, retry, or persistence.
- Escape, page navigation, camera loss, Live Input arming, and window close still erase volatile
  in-progress samples.
- Weak correlation, incomplete screen coverage, invalid eye features, timing faults, numerical
  instability, and incomplete acceptance policy all fail closed.
- Camera frames remain local and are not intentionally stored or uploaded.

## Verification

- `python -m pytest tests/unit/test_calibration_session.py tests/unit/test_calibration_mapper.py -q`
  - Result: 43 passed.
- `python -m ruff check src tests`
  - Result: passed.
- `python -m ruff format --check src tests`
  - Result: 160 files already formatted.
- `python -m mypy src tests`
  - Result: strict analysis passed for 160 source files.
- `scripts/check.ps1`
  - Result: documentation and icon verification passed; 161 files were formatted; Ruff passed;
    strict mypy passed for 160 source files; all 802 tests passed.
- Native Qt rendering at 1200x760
  - Result: verified the moving-target state with healthy live correlation and the fail-closed retry
    result with readable reason, sample count, nine-region coverage, and cancel/retry controls.

## Known limitations

- Physical-device accuracy evidence and justified production acceptance thresholds are still
  required; the default remains `Review Required`.
- Correlation confirms that feature movement follows the path but does not by itself prove a mapper
  is accurate; held-out fit evidence and the acceptance policy remain separate required gates.
- The trajectory is optimized for the primary display and does not calibrate multiple monitors.

## Exact next task

Collect representative physical-webcam sessions, record accuracy/latency evidence, and configure an
acceptance policy only if the measured distribution justifies its thresholds.
