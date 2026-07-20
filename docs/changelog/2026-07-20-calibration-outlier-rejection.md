# 2026-07-20 - Calibration outlier rejection

## Summary

Added robust per-target statistical outlier rejection to calibration collection. A target now
completes only when its bounded quota contains inliers; a feature that passes basic geometry gates
but varies too far from the stable target cluster is removed and explained in the UI.

## Added

- A pure, deterministic coordinate-wise median/MAD inlier selector.
- A minimum absolute radius for zero-MAD and near-identical sample groups.
- Stable input-order indices without sorting or mutating caller data.
- Inlier-only target progress and quota completion.
- Retroactive removal of an early outlier once a stable cluster becomes available.
- Plain-language statistical-outlier feedback in Calibration.

## Safety and quality decisions

- Filtering starts only after five samples, avoiding unstable statistics on tiny groups.
- Horizontal and vertical coordinates must independently remain within robust bounds.
- The MAD radius uses the normal-consistency scale and a conservative multiplier; the absolute
  floor prevents tiny numerical noise from rejecting an otherwise stable cluster.
- Rejected candidates still consume the target's bounded attempt budget and cannot be replayed.
- Filtering is per target; samples from other screen targets cannot influence its center or spread.
- No mapper, persistence, validation score, smoothing, screen coordinate, or pointer output was
  added.

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes\calibration src\meyes\ui\calibration_page.py tests\unit\test_calibration_outliers.py tests\unit\test_calibration_session.py tests\unit\test_calibration_ui.py
.\.venv\Scripts\python.exe -m mypy src\meyes\calibration src\meyes\ui\calibration_page.py tests\unit\test_calibration_outliers.py tests\unit\test_calibration_session.py tests\unit\test_calibration_ui.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_calibration_outliers.py tests\unit\test_calibration_session.py tests\unit\test_calibration_ui.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 35 passed in 0.53 seconds.

Full repository gate:

- Ruff format: 113 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 113 source files.
- Pytest: 579 passed in 15.15 seconds.

## Known limitations

- Median/MAD filtering improves sample consistency but is not an accuracy guarantee.
- A strongly multimodal cluster may require target retry rather than automatic interpretation.
- Mapper fitting, held-out validation, calibration persistence, and pointer output remain pending.

## Next task

Implement a replaceable calibration mapper with deterministic fit/predict contracts and held-out
validation, keeping pointer output disconnected.
