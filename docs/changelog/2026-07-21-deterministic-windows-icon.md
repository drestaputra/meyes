# 2026-07-21 - Deterministic Windows icon

## Summary

Derived a packager-neutral Windows ICO from the original MEYES SVG without installing a compiler or
selecting a standalone delivery tool.

## Added

- A deterministic generator that rasterizes the SVG through the locked Qt renderer and constructs
  a Windows ICO containing PNG frames at 16, 20, 24, 32, 40, 48, 64, 96, 128, and 256 pixels.
- Explicit write mode plus default byte-for-byte verification mode.
- Binary Git attributes, exact size/SHA-256 evidence, ICO directory/frame tests, and installed-wheel
  entry/hash verification.
- Quality-gate and submission-preflight requirements for the source, derivative, and verifier.

## Verification

- Generated size: 19,906 bytes.
- SHA-256: `64f9ad51118096b8103b8c2cefc7931d3fc4d196e92d59c70968ac8d9a8b48a9`.
- All ten directory entries point to bounded PNG frames with their declared dimensions.
- Repeated in-memory regeneration matches the committed asset exactly.
- The full gate passed: 159 formatted/linted Python files, strict mypy across 158 typed source/test
  files, and all 788 tests on native Windows Qt.

## Known limitations

No standalone packager is selected, so the ICO is not yet embedded into an executable or installer.
MSIX-specific image assets and installed Windows shell/taskbar appearance remain pending.

## Next task

Use this common asset in the isolated packager comparison once the external compiler/Nuitka
environment is provisioned.
