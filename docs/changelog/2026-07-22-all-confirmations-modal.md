# 2026-07-22 - All confirmations modal

## Summary

Removed the remaining user-entered confirmation controls and standardized guarded actions on
cancel-default modal dialogs.

## Changed

- Live Input no longer asks the user to type `ENABLE LIVE INPUT`; its enabled Arm button opens a
  destructive safety dialog and consumes the decision only for that arm attempt.
- Cancelling the Live Input dialog does not request a window handle, register the emergency hotkey,
  run the physical-input preflight, construct an executor, or leave Safe Mode.
- Profile deletion no longer asks the user to copy the selected name into a text field.
- Restore Default no longer requires a confirmation checkbox.
- First-run completion no longer requires an acknowledgement checkbox; Finish opens a separate
  orientation-completion dialog.
- Submission preflight now requires the modal-consent claim and rejects a return of the removed Live
  Input phrase in README.
- Profile restore and delete buttons now open action-specific dialogs and do nothing on cancel.
- Ordinary data inputs such as profile names, import names, and binding parameters remain text fields
  because they provide operation data rather than confirmation.

All running-camera, Windows-platform, emergency-hotkey, physical-input, release-first, inactive-only,
built-in protection, and recovery-backup boundaries remain enforced by their controllers.

## Verification

- Controller tests reject missing consent/confirmation without native or persistence work.
- Page tests cover cancel and accept paths for Live Input, profile restore, and profile deletion.
- Native visual smoke confirmed that Live Input has no phrase field, its warning modal is readable,
  and Profiles exposes direct Restore/Delete buttons without confirmation inputs or overflow.
- The full local gate passed: documentation and ICO verification, Ruff, strict mypy across 160 typed
  source/test files, and all 792 tests on native Windows Qt.
- Exact-revision remote Windows CI must pass before completing the iteration.

## Known limitations

Actual Live Input remains an optional disposable-target hardware safety check and is never required
for ordinary Safe Mode review.

## Next task

Complete the pending human keyboard-only review of all native dialogs and the full-screen calibration
flow.
