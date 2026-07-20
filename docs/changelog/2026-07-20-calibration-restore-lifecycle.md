# 2026-07-20 - Calibration restore lifecycle

## Summary

Added lifecycle coordination for deleted-calibration restore. Fake provisioning is cleared first;
the repository restores and validates an exact backup; fake diagnostics then checks current geometry.
Incompatible or failed provisioning clears again and rolls back only the unchanged active copy.

## Added

- Restore and rollback operations on the narrow calibration-store protocol.
- Typed restored lifecycle result and read-only catalog passthrough.
- Repository rollback that compares active and retained backup bytes before unlinking the active copy.
- Tests for successful lifecycle ordering, display mismatch ordering, exact-copy rollback, and refusal
  to remove a changed active file.

## Safety decisions

- Fake provisioning is cleared before repository restore begins.
- A restored calibration is usable only when current native geometry exactly matches provenance.
- Rollback cannot remove an active file whose bytes differ from the retained restore source.
- The original deleted backup remains after successful restore and rollback.
- Rollback failure reports manual-review state rather than claiming the active file is safe.
- No UI or Live Input path calls restore yet.

## Verification

Focused Ruff and strict mypy passed; 35 persistence and lifecycle tests passed in 1.45 seconds.

Full repository gate:

- Ruff format: 138 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 138 source files.
- Native Windows pytest: 714 passed in 20.24 seconds.

## Known limitations

- Restore is not exposed in Calibration UI.
- Backup catalog metadata is not visible to users.
- Manual review is required if an external process changes the active file during rollback.

## Next task

Expose only the newest deleted backup's timestamp and size in Calibration UI, require an exact
`RESTORE SAVED CALIBRATION` phrase, and keep Live Input state unchanged during lifecycle restore.
