# 2026-07-21 - Packaged application icon

## Summary

Added an original SVG application icon and wired it through Qt's application-level window icon so
the main window and availability-gated tray use the same asset. Native fallback remains available if
the optional icon cannot be resolved.

## Asset and packaging

- Repository-native 64×64 vector using only the locked accent/surface/ink design roles.
- Original eye mark; no Hallmark code, generated artifact, screenshot, or external artwork copied.
- MIT-licensed source, exact 524-byte size, and recorded SHA-256.
- Packaged/source-tree resolver prefers installed wheel assets and returns a null native fallback if
  neither exists.
- Hatch wheel includes the SVG and its provenance README.
- Isolated wheel verification requires both entries and independently checks exact icon size/hash.

## Verification

- Qt rendered the SVG to a non-null 256×256 preview.
- Resolver/load/fallback tests: 3 passed.
- Focused Ruff and strict mypy passed.
- Isolated wheel entry, install, model/license diagnostic, and icon integrity verification passed.

## Remaining delivery work

The SVG is the source of truth. A selected standalone Windows packager must still derive and verify
its required ICO/MSIX sizes and confirm installed shell/taskbar/tray appearance on a clean machine.
