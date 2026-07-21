# 2026-07-20 - Permanent calibration backup deletion

## Summary

Added an intentionally narrow way to permanently remove the newest recoverable calibration backup.
The operation requires `DELETE CALIBRATION BACKUP PERMANENTLY` exactly and targets one current
catalog record rather than a wildcard or directory.

## Added

- Repository deletion of one exact `DeletedCalibrationBackup` record.
- Fresh bounded-catalog membership, configured-directory containment, regular-file, link/reparse,
  and byte-size checks immediately before deletion.
- A lifecycle result that does not clear or reprovision cursor state.
- Calibration-page exact phrase and destructive-action control for the newest backup only.
- Composition-root logging and metadata refresh after success or failure.
- Repository, lifecycle, and end-to-end UI regression coverage.

## Safety behavior

- The active `accepted-calibration.json` path is never accepted as a deletion target.
- Stale or modified metadata is rejected and the file is retained.
- Symlinks and Windows reparse points are excluded from the catalog and rejected before deletion.
- The retained active copy and Live Input state are unchanged.
- Deletion is permanent and the UI labels it accordingly.

## Visual QA

Native Windows bottom-scroll renders at 900 x 640 and 1200 x 760 show the new confirmation field
and button fully accessible. The horizontal scrollbar maximum remains zero at both sizes.

## Verification

Focused Ruff format/lint, strict mypy, and `71 passed` completed first. The full repository gate
then passed: Ruff format and lint, strict mypy across 138 source files, and `732 passed`.

## Next task

Run the full deterministic gate, then begin evidence tooling for Windows scaling and broad physical
screen reach without automating unsupported display-setting changes.
