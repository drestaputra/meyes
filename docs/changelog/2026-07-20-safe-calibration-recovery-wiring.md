# 2026-07-20 - Safe calibration recovery wiring

## Summary

Connected accepted-calibration persistence to the application composition root. Newly accepted
fits are saved under the same `AppPaths` used by configuration, and a valid envelope is recovered
once during startup into fake-only diagnostics while Live Input remains SAFE.

## Added

- Read-only `ConfigManager.paths` access for correctly scoped related repositories.
- Production lifecycle construction with an injectable calibration store and geometry provider.
- One-shot startup recovery before camera tracking begins.
- Automatic storage of only newly policy-accepted fit results.
- A sanitized Saved calibration row in the Calibration page.
- Event-only startup recovery logging with a quarantine boolean and no private payload values.

## Safety decisions

- `LiveInputController` is constructed SAFE before recovery and is not passed to the lifecycle.
- Recovery cannot restore typed consent, register a hotkey, construct an executor, or arm output.
- Review-required and rejected fits clear fake diagnostics and never write calibration data.
- Replacement clears the old pipeline before saving and reprovisions only validated accepted proof.
- Storage failure leaves a valid accepted fit volatile and fake-only for the current process.
- UI and logs omit mapper coefficients, policy thresholds, raw errors, and filesystem paths.

## Verification

Focused Ruff and strict mypy passed; 11 `MainWindow` tests and 43 related wiring tests passed. The
integration cases verify both saved-fit recovery and new-fit storage while Live Input remains SAFE.

Full repository gate:

- Ruff format: 138 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 138 source files.
- Native Windows pytest: 694 passed in 19.83 seconds.

## Known limitations

- No explicit user-facing replace, forget, or invalidation control exists yet.
- Calibration provenance is limited to policy and validation evidence; camera/display identity and
  age are not yet stored.
- Scaling-matrix physical-device QA and all gaze pointer output remain pending.

## Next task

Persist and display bounded calibration provenance (creation time plus primary-display geometry)
and fail recovery closed when the current display geometry no longer matches the accepted envelope.
