# 2026-07-20 - Explicit-consent pointer safety

## Summary

Audited the calibrated `SendInput` pointer integration and removed camera-start auto-arming. MEYES
now remains in Safe Mode when the camera starts and requires the user to type
`ENABLE LIVE INPUT` before every arm.

## Changed

- Removed the composition-root path that supplied the consent phrase programmatically.
- Retained accepted-calibration cursor candidates and their armed-only Live Input connection.
- Restored per-session consent language in the Live Input page, README, privacy boundary, judge
  guide, submission record, TODO, and top-level changelog.
- Made optional native API and screen-geometry dependency selection use explicit `None` checks.

## Safety invariants

- Camera startup cannot register the emergency hotkey, construct the executor, or leave Safe Mode.
- A cursor candidate is ignored unless Live Input is already armed.
- Consent and armed state are never persisted or recovered from calibration storage.
- Every disarm requires the exact phrase again.

## Verification

The deterministic composition-root regression asserts that a transition to camera `Running`
leaves Live Input safe, performs no native registration, and makes no executor call. The complete
gate passed: Ruff format and lint, strict mypy across 138 source files, and `720 passed`.

## Next task

Bind pointer execution to the exact accepted display provenance and add display-change fail-closed
coverage before collecting physical scaling-matrix evidence.
