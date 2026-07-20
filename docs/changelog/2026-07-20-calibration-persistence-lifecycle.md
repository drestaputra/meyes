# 2026-07-20 - Calibration persistence lifecycle

## Summary

Added a disconnected lifecycle coordinator between accepted-calibration storage and fake-only
cursor provisioning. It establishes deterministic teardown/save/reprovision ordering and one-shot
startup recovery before either behavior is connected to the application composition root.

## Added

- Narrow runtime protocols for an accepted-calibration store and no-executor cursor provisioner.
- Typed disabled, empty, recovered, saved, volatile, and faulted lifecycle results.
- Cached one-shot recovery that cannot repeat native provisioning or disk reads accidentally.
- Storage-fault fallback that restores only the valid volatile fake diagnostics pipeline.
- Quarantine-path propagation for bounded UI/log reporting in a future wiring iteration.

## Safety decisions

- Replacement clears the old cursor pipeline before any atomic storage operation begins.
- Missing acceptance clears provisioning and never writes.
- Missing policy or storage keeps accepted calibration volatile rather than inventing persistence.
- A disk write failure cannot destroy the current valid volatile calibration candidate.
- The coordinator imports no Live Input controller, accepts no executor, and changes no consent or
  arming state.
- `MainWindow` does not call this coordinator yet.

## Verification

Focused Ruff and strict mypy passed; 6 lifecycle tests passed in 0.63 seconds.

Full repository gate:

- Ruff format: 138 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 138 source files.
- Native Windows pytest: 692 passed in 18.97 seconds.

## Known limitations

- Application startup recovery and newly accepted-fit persistence are not wired.
- Persistence status is not yet exposed in Calibration UI or structured application logs.
- There is no in-app forget/delete control for a stored calibration.

## Next task

Wire the lifecycle at the composition root using the same `AppPaths` as configuration, recover once
while Live Input is still SAFE, persist newly accepted fits, and expose only sanitized status.
