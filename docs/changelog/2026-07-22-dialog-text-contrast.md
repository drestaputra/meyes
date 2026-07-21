# 2026-07-22 - Dialog text contrast

## Summary

Fixed unreadable dark text on a dark native surface in app-themed confirmation dialogs.

## Fixed

- App-owned confirmation dialogs now use the theme's explicit light surface and dark ink colors.
- Confirmation message labels and button text receive explicit readable foreground colors.
- Tooltips use the same surface/ink pairing instead of relying on an incompatible inherited native
  palette.
- Windows High Contrast behavior remains system-owned because MEYES disables its custom stylesheet
  when that accessibility mode is active.

## Verification

- A native Qt regression test verifies the rendered dialog, message, and button palette roles while
  the full MEYES stylesheet is inherited from the parent window.
- A native visual smoke confirmed dark message/button text on the explicit white modal surface with
  visible Cancel focus.
- The full local gate passed: documentation and ICO verification, Ruff, strict mypy across 160
  typed source/test files, and all 792 tests on native Windows Qt.
- Exact-revision remote Windows CI must pass before completing the iteration.

## Known limitations

Enabled Windows High Contrast and 125%/150% scaling still require the separately tracked human
visual and keyboard checks.

## Next task

Complete the enabled Windows High Contrast visual/keyboard evidence row on representative hardware.
