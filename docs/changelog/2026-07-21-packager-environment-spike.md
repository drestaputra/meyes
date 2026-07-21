# 2026-07-21 - Packager environment spike

## Summary

Measured local prerequisites for the Phase 7 packager decision without installing a compiler or
mutating the locked environment. Kept the selection explicitly open because no standalone build was
produced.

## Result

- Official `pyside6-deploy` wrapper present with PySide6 6.11.1.
- Nuitka and every checked C/C++ toolchain/dependency-reader route absent.
- Temporary standalone spec generation passed with UTF-8 without BOM and reported missing
  `dumpbin` plus a `Nuitka==4.0` requirement.
- Defined the isolated, pinned, inspectable standalone-first comparison needed before selection.
- No executable, installer, certificate, package upload, or system/toolchain mutation occurred.

Full evidence: [`docs/evidence/packaging/2026-07-21.md`](../evidence/packaging/2026-07-21.md).
