# 2026-07-21 - Display scaling evidence probe

## Summary

Added a read-only native Windows probe so each 100%, 125%, and 150% scaling configuration can be
recorded with the same schema instead of relying on screenshots or memory. The current 100% host
configuration is committed as the first matrix row.

## Added

- `GetDpiForSystem` behind a narrow testable ctypes reader.
- A schema-1 evidence record containing UTC capture time, native physical primary-screen geometry,
  Windows system DPI/scale, Qt logical primary geometry, and Qt device-pixel ratio.
- Separate checks for Qt scaled-size/native agreement and Qt DPR/Windows scale agreement.
- Exclusive-create JSON output that refuses to replace earlier evidence.
- A PowerShell capture entry point and documented three-row evidence matrix.
- Deterministic tests for 100%, 125%, 150%, inconsistent Qt state, invalid DPI, unsupported
  platform, and non-overwriting output.

## Native evidence

The current host reported:

- physical primary screen: 1920 x 1080 at (0, 0);
- system DPI: 96, reported scale: 100%;
- Qt logical screen: 1920 x 1080, DPR 1.0;
- both consistency checks: passed.

This is evidence only for 100%. The 125% and 150% rows remain pending a human-controlled Windows
display change; the tool never changes display configuration itself.

## Verification

Focused Ruff format/lint, strict mypy, and `16 passed` completed first. The full repository gate
then passed: Ruff format and lint, strict mypy across 140 source files, and `740 passed`.

## Next task

Run the full deterministic gate, then use this probe and native layout screenshots after the user
selects 125% and 150% scaling.
