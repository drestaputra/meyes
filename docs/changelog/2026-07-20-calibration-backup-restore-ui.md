# 2026-07-20 - Calibration backup restore UI

## Summary

Exposed the newest recoverably deleted calibration backup in Calibration UI and added an exact-
phrase restore action. The UI delegates to the guarded repository/lifecycle path and never handles
envelope contents or filesystem paths.

## Added

- Newest deleted backup UTC timestamp and byte-size status.
- `RESTORE SAVED CALIBRATION` exact case-sensitive confirmation.
- Automatic catalog refresh after forget and restore attempts.
- Sanitized restored, incompatible, and fault application events.
- Composition-root test covering forget then restore with active copy, retained backup, fake-only
  suspended diagnostics, and unchanged Live Input SAFE state.

## Safety decisions

- Only the newest bounded catalog record is selectable; paths and payload details are hidden.
- Restore stays disabled until a valid backup exists and the exact phrase is present.
- Repository checksum/policy/provenance validation and lifecycle geometry/rollback gates remain the
  authority; UI metadata is never trusted as validation.
- Both confirmation inputs are cleared after use.
- Restore does not construct an executor or change Live Input consent/arming state.

## Verification

Focused Ruff and strict mypy passed; 60 calibration persistence/lifecycle/UI/window tests passed in
7.10 seconds, with 12 composition-root tests passing in 5.95 seconds after import cleanup.

Full repository gate:

- Ruff format: 138 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 138 source files.
- Native Windows pytest: 714 passed in 20.44 seconds.

## Known limitations

- Only the newest deleted backup can be restored through UI.
- Deleted backups cannot be permanently removed in-app.
- Scaling-matrix physical-device QA and all gaze pointer output remain pending.

## Next task

Run a native Windows visual QA pass on the expanded Calibration page at minimum and target window
sizes, then refine layout/accessibility without weakening confirmation gates.
