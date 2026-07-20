# 2026-07-20 - Replaceable calibration mapper

## Summary

Added a dormant, replaceable quadratic mapper from binocular eye-relative features to normalized
screen coordinates. Fitting fails closed on incomplete or unsafe geometry and produces deterministic
per-target holdout metrics before returning a final all-sample model. The UI and pointer path do not
consume this mapper yet.

## Added

- A runtime-checkable `CalibrationMapper` prediction protocol.
- An immutable six-term quadratic polynomial model for independent screen X/Y prediction.
- Complete nine-target coverage and minimum-per-target sample requirements.
- Finite-input, full matrix-rank, condition-number, coefficient, and output guards.
- Deterministic sample ordering and per-target holdout selection.
- Normalized Euclidean RMSE, mean-error, maximum-error, and sample-count metrics.
- Final refitting on all accepted samples after holdout evaluation.

## Safety and quality decisions

- Prediction is intentionally unclamped so validation can reveal boundary error rather than hiding
  it as a plausible screen-edge result.
- The mapper reports metrics but does not invent a universal pass threshold before real-device
  measurement establishes one.
- Rank-deficient and ill-conditioned feature geometry raises a recoverable fit failure.
- Replaceable protocol implementations are checked for the correct finite output type during
  evaluation.
- No model is persisted, activated, smoothed, converted to pixels, or sent to `SendInput`.

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes\calibration\mapper.py tests\unit\test_calibration_mapper.py
.\.venv\Scripts\python.exe -m mypy src\meyes\calibration\mapper.py tests\unit\test_calibration_mapper.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_calibration_mapper.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 12 passed in 0.42 seconds.

Full repository gate:

- Ruff format: 115 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 115 source files.
- Pytest: 591 passed in 17.96 seconds.

## Known limitations

- Holdout metrics use samples from the same collection session and are not a cross-session accuracy
  guarantee.
- Head-pose features and explicit pose compensation are not included in this mapper.
- The Calibration page does not fit, display, accept, or persist a mapper yet.

## Next task

Wire guarded fit/validation into the completed collection state, present honest metrics and retry,
and keep the mapper volatile until persistence/recovery semantics are designed.
