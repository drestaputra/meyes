# 2026-07-20 - Primary-screen coordinate mapper

## Summary

Added a dormant mapping boundary from normalized predictions to validated primary-screen physical
pixels. It clamps transparently, uses inclusive endpoints, and has no executor dependency.

## Added

- `PhysicalScreenGeometry`, `PhysicalScreenPoint`, and observable `ScreenMappingResult` contracts.
- Replaceable `ScreenCoordinateMapper` protocol and `PrimaryScreenMapper` implementation.
- Signed 32-bit origin/bounds validation and deterministic nearest-pixel rounding.
- Per-axis clamping evidence for diagnostics and future safety policy.
- Tests for corners, center, negative origin, 1x1 geometry, invalid bounds, and non-finite input.

## Safety and quality decisions

- Geometry is explicitly physical pixels; Qt logical geometry is not silently treated as native.
- Width/height map to inclusive `extent - 1` endpoints, preventing an off-screen final pixel.
- Clamping is observable rather than hidden.
- No screen API, timer, accepted calibration, smoothing pipeline, or executor is connected.

## Verification

Focused Ruff, strict mypy, and pytest passed; 23 focused tests passed in 0.45 seconds.

Full repository gate:

- Ruff format: 124 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 124 source files.
- Native Windows pytest: 642 passed in 15.55 seconds.

## Known limitations

- DPI-aware native primary-screen acquisition is not implemented.
- Mapper persistence, freeze/resume, runtime scheduling, and pointer output remain pending.

## Next task

Build the dormant temple-interaction cursor freeze/resume state machine with monotonic timing and
tracking-loss reset, without connecting pointer output.
