# 2026-07-20 - Fake-only cursor pipeline

## Summary

Composed accepted calibration, adaptive smoothing, physical-pixel mapping, and the cursor movement
gate into an inspectable pipeline with no input-executor dependency. A pixel candidate is returned
only when calibration carries explicit acceptance proof, gaze is available, and the gate is open.

## Added

- `AcceptedCalibration`, which rejects review-required or rejected fit outcomes.
- Controller access to an accepted token only after configured policy approval.
- Ready, gate-blocked, and feature-unavailable pipeline results.
- Smoothing reset on temple freeze, tracking suspension, unavailable gaze, and lifecycle reset.
- Tests proving blocked results contain no normalized or pixel candidate.
- End-to-end domain tests for accepted prediction, smoothing, mapping, hold freeze, delayed resume,
  and unavailable-feature handling.

## Safety decisions

- The pipeline constructor requires the proof-carrying accepted token, not a bare fitted mapper.
- It owns no executor and cannot move the pointer.
- Blocked/unavailable updates reset filter history and expose no screen candidate.
- Lifecycle methods remain explicit; the application does not construct this pipeline yet.

## Verification

Focused Ruff, strict mypy, and pytest passed; 48 focused tests passed in 1.63 seconds.

Full repository gate:

- Ruff format: 128 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 128 source files.
- Native Windows pytest: 654 passed in 15.67 seconds.

## Known limitations

- No Qt lifecycle, Diagnostics, native screen acquisition, persistence, timer, or pointer output.
- Default calibration policy still requires review because physical evidence is pending.

## Next task

Add a Qt-owned fake-only cursor diagnostics controller with freshness expiry and lifecycle wiring,
without constructing or invoking the native input executor.
