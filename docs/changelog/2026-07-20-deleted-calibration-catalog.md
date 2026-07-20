# 2026-07-20 - Deleted calibration catalog

## Summary

Added bounded read-only repository metadata for recoverably deleted accepted-calibration backups.
This creates a safe discovery boundary before any restore workflow is implemented.

## Added

- Strict parsing of `accepted-calibration.deleted-YYYYMMDD-HHMMSS-ffffff.json` names.
- Newest-first deletion timestamp and byte-size metadata.
- A maximum of 20 visible backup records with a sanitized omission warning.
- Tests for ordering, bounding, malformed names, unchanged ignored files, and symlink refusal.

## Safety decisions

- Cataloging does not open, parse, hash, move, rename, or delete backup payloads.
- Links, Windows reparse points, non-regular files, and malformed timestamps are ignored.
- Unsafe or unavailable data directories produce an empty catalog with a bounded warning.
- Full paths remain repository-internal and are not exposed in UI or logs.
- Restore remains unavailable.

## Verification

Focused Ruff and strict mypy passed; 17 persistence tests passed in 1.04 seconds.

Full repository gate:

- Ruff format: 138 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 138 source files.
- Native Windows pytest: 705 passed in 18.00 seconds.

## Known limitations

- The catalog is not yet displayed to the user.
- Metadata alone does not prove a backup payload is valid.
- Restore must still revalidate size, JSON ambiguity, checksum, policy, and display geometry.

## Next task

Add repository-level guarded restore of one exact catalog record into the active envelope only when
no active envelope exists, retaining the deleted backup if validation or atomic activation fails.
