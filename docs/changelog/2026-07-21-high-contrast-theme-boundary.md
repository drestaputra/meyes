# 2026-07-21 - High Contrast theme boundary

## Summary

Added a narrow read-only Windows High Contrast preference probe and an adaptive shell boundary. When
the preference is enabled, MEYES omits its custom QSS palette so Qt and Windows supply system colors
and native focus rendering.

## Safety and accessibility

- Uses `SystemParametersInfoW(SPI_GETHIGHCONTRAST)` only to read the current flag.
- Never changes a Windows accessibility preference.
- Native read failure falls back to the normal MEYES stylesheet without affecting camera/input.
- An explicit constructor override supports deterministic enabled-mode verification.
- Safe/Live, camera, fault, and lifecycle states retain textual labels rather than relying on color.
- First-run, settings, privacy, and tray behavior are unchanged.

## Verification

- Two fake API tests cover enabled, disabled, and native-read failure.
- MainWindow integration verifies an empty custom stylesheet plus retained Safe Mode/accessibility
  text when enabled mode is forced.
- The current native Windows probe reports disabled; actual enabled-theme human visual/keyboard QA
  remains pending and is not claimed.
- Ruff formatting/lint and strict mypy passed across 154 source files; all 773 tests passed on native
  Windows Qt.
