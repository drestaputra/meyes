# 2026-07-20 - Recoverable calibration forget

## Summary

Added an exact-phrase Calibration control that forgets the active accepted-calibration envelope.
Fake cursor provisioning is cleared first, then the envelope is moved to a timestamped deleted
backup so the action remains recoverable outside the application.

## Added

- Repository `forget` support using same-directory `accepted-calibration.deleted-*.json` moves.
- Lifecycle forgotten state with clear-before-storage ordering and fault containment.
- Inline `FORGET SAVED CALIBRATION` confirmation with no modal dialog.
- Sanitized success/fault application events and Calibration status text.
- Tests covering the backup bytes, missing file, ordering, storage fault, UI phrase gate, pipeline
  clearing, and unchanged Live Input SAFE state.

## Safety decisions

- The button is disabled until the exact case-sensitive phrase is present.
- No file is permanently deleted; the active envelope is moved on the same local data volume.
- Existing deleted backups are never overwritten.
- Fake provisioning is cleared even if the storage move fails.
- The workflow has no `LiveInputController` dependency and changes no consent or arming state.
- UI and logs do not disclose the backup path, coefficients, policy, or native error.

## Verification

Focused Ruff and strict mypy passed; 49 persistence/lifecycle/UI/window tests passed, including 12
composition-root tests in 5.59 seconds.

Full repository gate:

- Ruff format: 138 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 138 source files.
- Native Windows pytest: 703 passed in 20.50 seconds.

## Known limitations

- Deleted backups require manual restore or permanent deletion outside MEYES.
- The UI does not list backup timestamps or contents.
- Scaling-matrix physical-device QA and all gaze pointer output remain pending.

## Next task

Add read-only stored/deleted calibration catalog metadata, then a guarded restore action that still
revalidates checksum, policy, and current display geometry before provisioning.
