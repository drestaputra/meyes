# 2026-07-20 - Adaptive cursor smoothing

## Summary

Added a dormant two-axis One Euro filter for future normalized gaze predictions. The filter reduces
small jitter with a low cutoff, raises each axis cutoff independently as movement speed increases,
and resets instead of interpolating across stale tracking gaps. It is not wired to calibration,
pixels, a timer, or operating-system pointer output.

## Added

- Immutable `OneEuroFilterSettings` with minimum cutoff, speed coefficient, derivative cutoff, and
  maximum-gap controls.
- A stateful `OneEuroPointFilter` for independent normalized X/Y smoothing.
- Strictly increasing finite monotonic timestamps and mutation-free rejection of invalid order.
- Mutation-free rejection when extreme finite values overflow derivative, cutoff, or output math.
- First-sample pass-through, explicit lifecycle reset, and stale-gap reseeding.
- A validated backward-compatible `cursor` configuration section with local filter defaults.
- Deterministic tests for jitter reduction, rapid movement response, independent axes, stale gaps,
  reset, timestamp errors, invalid points, invalid settings, and old schema-one documents.

## Safety and quality decisions

- The filter does not clamp its normalized input; later validation and screen mapping must retain
  responsibility for bounds.
- A stale gap returns the new raw point as a seed rather than creating a long artificial glide from
  obsolete gaze history.
- Duplicate and out-of-order timestamps raise before state mutation.
- Reset is intended for tracking suspension, mapper replacement, profile transitions, and shutdown.
- No application controller constructs the filter and no executor receives its output.

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes\cursor src\meyes\config\models.py tests\unit\test_cursor_smoothing.py tests\unit\test_config_manager.py
.\.venv\Scripts\python.exe -m mypy src\meyes\cursor src\meyes\config\models.py tests\unit\test_cursor_smoothing.py tests\unit\test_config_manager.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_cursor_smoothing.py tests\unit\test_config_manager.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 26 passed in 0.86 seconds.
- Synthetic alternating jitter mean absolute deviation fell from `0.020000` to `0.001190`
  (`94.1%`) after warm-up with the fixed low cutoff used by the test.
- On the synthetic one-frame `0.1 -> 0.9` step, the adaptive configuration advanced to `0.202927`
  versus `0.139804` for the fixed-cutoff configuration.

Full repository gate:

- Ruff format: 122 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 122 source files.
- Native Windows pytest: 631 passed in 15.62 seconds.

## Known limitations

- Synthetic replay improvement is not a physical-device accuracy or latency claim.
- Default parameters have not been tuned with representative users or cameras.
- The filter is not wired to a mapper, freeze/resume gate, pixel conversion, timer, or pointer.
- Primary-screen reach validation, mapper persistence, and multi-monitor support remain pending.

## Next task

Build a dormant primary-screen coordinate mapper with explicit clamping, dimension/DPI validation,
and fake-boundary tests, still without scheduling or sending operating-system pointer movement.
