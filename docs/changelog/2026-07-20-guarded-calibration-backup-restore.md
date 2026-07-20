# 2026-07-20 - Guarded calibration backup restore

## Summary

Added repository-level restoration of one exact deleted-calibration catalog record. Restore fully
revalidates the stored envelope before exclusively creating the active file, and always retains the
deleted backup.

## Added

- Shared bounded envelope decoding for active load and deleted-backup validation.
- Explicit policy-mismatch handling that preserves valid but incompatible data.
- Exact current catalog-record identity checks including path, deletion timestamp, and byte size.
- Exclusive active-envelope creation with flush/fsync and partial-file cleanup on write failure.
- Tests for success, active collision, checksum tampering, stale metadata, and missing policy.

## Safety decisions

- Restore cannot overwrite any active path, including an unexpected file or link.
- Validation occurs before active-file creation and includes size, non-link regular-file type,
  duplicate JSON keys, schema, checksum, finite fields, exact policy, and accepted evidence.
- The deleted backup is retained after both successful and failed restore attempts.
- A restore request must use an exact record from the current bounded catalog.
- No lifecycle, UI, provisioning, or Live Input behavior is connected in this iteration.

## Verification

Focused Ruff and strict mypy passed; 22 persistence tests passed in 1.14 seconds.

Full repository gate:

- Ruff format: 138 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 138 source files.
- Native Windows pytest: 710 passed in 19.79 seconds.

## Known limitations

- Restore is not exposed through lifecycle or UI.
- Display geometry is decoded but current geometry comparison remains the lifecycle's responsibility.
- Only the 20 newest catalog records are eligible for the future restore UI.

## Next task

Add lifecycle restore ordering: clear fake provisioning, restore the exact backup, provision only
after current geometry matches provenance, and roll the new active envelope back if provisioning
fails or geometry differs.
