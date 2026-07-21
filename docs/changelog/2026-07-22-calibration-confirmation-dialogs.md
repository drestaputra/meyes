# 2026-07-22 - Calibration confirmation dialogs

## Summary

Replaced the four typed phrase fields shown in Calibration with direct action buttons and explicit
modal confirmations.

## Changed

- Replace, Forget, Restore, and Permanently delete now open action-specific dialogs.
- Cancel is the default button and Escape action for every dialog.
- Destructive actions use warning presentation and unambiguous confirm labels.
- Cancel never calls the persistence lifecycle operation.
- Replace remains disabled unless a saved replacement is pending; Restore and Delete remain disabled
  unless an exact newest backup is cataloged.

The underlying release-first replacement, pipeline clearing, checksum/policy/display revalidation,
exact backup-record targeting, and unchanged Live Input boundaries remain in place. The separate
`ENABLE LIVE INPUT` typed consent is intentionally retained because it arms operating-system input.

## Verification

- Real modal tests cover cancel/default/Escape configuration and positive confirmation.
- Calibration/MainWindow tests cover cancel, replace release failure/retry, forget, restore, and
  permanent deletion through the new buttons.
- A native 900x640 visual smoke confirmed that the phrase fields are gone, all four action buttons
  remain reachable, and the destructive dialog presents Cancel as the default action.
- The full local gate passed: documentation and ICO verification, Ruff, strict mypy across 160
  typed source/test files, and all 791 tests on native Windows Qt.
- Remote Windows CI must pass on the exact pushed revision before completing the iteration.

## Known limitations

Human keyboard/screen-reader review of the native modal dialogs remains part of accessibility QA.

## Next task

Perform native visual and keyboard review of Calibration at minimum size and Windows scaling rows.
