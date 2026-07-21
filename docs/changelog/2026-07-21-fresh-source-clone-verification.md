# 2026-07-21 - Fresh source clone verification

## Summary

Cloned the current Git revision into a unique temporary directory, created isolated tooling and
project environments, synchronized the committed lockfile, imported the package entry point, and
ran the complete deterministic gate successfully.

## Evidence

- Revision: `65b2e48a1c1826ff62ad97c3d7ed8690a08ebc89`.
- CPython 3.11.15 selected by uv.
- 43 locked dependencies plus editable MEYES installed.
- Package and `meyes.__main__.main` import passed.
- Ruff format/lint and strict mypy passed across 140 source files.
- Pytest: `740 passed in 22.03s`.

## Correction during verification

The host had no global `uv` launcher. A first command therefore stopped before sync. An isolated
bootstrap environment installed uv, and the gate was rerun with explicit fail-fast exit checks.
The initial smoke also referenced a nonexistent old module name; the real configured entry point,
`meyes.__main__.main`, passed on rerun.

## Limitations

This is a fresh source/environment check on the same Windows 11 host. It does not prove GitHub judge
access, Windows 10 compatibility, clean-user camera permissions, live webcam behavior, or real OS
input. Those remain separate human/external checks.

## Next task

Keep the source evidence current at the final submitted revision and perform the remaining live
clean-user check before the Devpost deadline if a second environment is available.
