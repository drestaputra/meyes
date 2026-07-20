# 2026-07-20 - Configured fake cursor dynamics

## Summary

Connected validated `AppConfig.cursor` values to construction of the accepted fake-only cursor
diagnostics pipeline. Previously, the production provisioner constructed the domain filter and gate
with their defaults even when configuration supplied different validated values.

## Changed

- `CursorPipelineProvisioner` now accepts immutable One Euro and cursor-gate settings.
- Every newly provisioned or recovered pipeline receives fresh filter and gate instances using those
  settings, so no state leaks across calibration replacement.
- `MainWindow` passes `config.cursor.filter_settings` and `config.cursor.gate_settings` explicitly.
- Cursor configuration wording now describes fake diagnostics consumption without implying output.

## Safety decisions

- Settings remain strictly validated by Pydantic and the domain dataclasses before provisioning.
- A new pipeline still requires proof-carrying accepted calibration and native geometry.
- Each replacement resets and discards prior smoothing/gate history.
- Tracking suspension remains mandatory even if temple freeze is configured off.
- No executor is accepted or constructed by this path.

## Verification

Focused Ruff and strict mypy passed; 38 provisioning, lifecycle, window, and configuration tests
passed in 6.08 seconds.

Behavioral coverage verifies a configured 500 ms resume delay and a low-cutoff, zero-speed-coefficient
filter response distinct from the defaults.

Full repository gate:

- Ruff format: 138 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 138 source files.
- Native Windows pytest: 696 passed in 19.07 seconds.

## Known limitations

- Sensitivity UI does not yet edit these values.
- Stored calibration provenance and display-geometry invalidation remain pending.
- All gaze pointer output remains disconnected.

## Next task

Extend accepted-calibration provenance with creation time and physical primary-display geometry,
then refuse startup recovery when the current display geometry differs.
