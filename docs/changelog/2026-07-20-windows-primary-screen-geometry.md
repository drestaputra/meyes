# 2026-07-20 - Windows primary-screen geometry

## Summary

Added read-only acquisition of the Windows primary monitor's physical-pixel rectangle. The
provider temporarily enters a Per-Monitor V2 thread DPI-awareness scope, reads `GetMonitorInfoW`,
and restores the previous context before returning validated geometry.

## Added

- A narrow injectable Windows geometry API for deterministic native-boundary tests.
- A ctypes User32 adapter for thread DPI scope, primary-monitor lookup, and monitor information.
- Conversion of exclusive native rectangle edges into validated physical-screen origin and size.
- Tests covering negative origins, unsupported platforms, malformed rectangles, query faults, and
  restoration faults.

## Safety decisions

- DPI awareness is scoped to the calling thread and always restored in `finally`.
- A failed restoration prevents a geometry result from escaping.
- No Qt logical coordinates are accepted and no guessed fallback dimensions exist.
- This provider has no executor dependency and performs no pointer, keyboard, or mouse output.
- Production cursor diagnostics remain unavailable; this iteration does not connect the provider.

## Verification

Focused Ruff and strict mypy passed; 8 focused tests passed.

Native read-only smoke on Windows returned
`PhysicalScreenGeometry(left=0, top=0, width=1920, height=1080)` and restored the prior thread DPI
context.

Full repository gate:

- Ruff format: 132 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 132 source files.
- Native Windows pytest: 669 passed in 20.48 seconds.

## Known limitations

- Production pipeline construction, accepted calibration persistence, scaling-matrix device QA,
  and all gaze pointer output remain pending.
- The current provider intentionally targets only the Windows primary monitor.

## Next task

Construct the production fake-only diagnostics pipeline only when both proof-carrying accepted
calibration and validated native geometry are available, while keeping every executor disconnected.
