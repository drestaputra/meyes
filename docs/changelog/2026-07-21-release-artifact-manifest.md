# 2026-07-21 - Release artifact manifest

## Summary

Added a fail-fast maintainer script for producing a reviewable Python wheel handoff without implying
that MEYES has a standalone executable, installer, signature, or automated publication path.

## Gates and output

- Requires a clean `main` worktree whose exact SHA matches both local and live `origin/main`.
- Runs frozen dependency sync, package entry-point smoke, Ruff, strict mypy, all tests, and isolated
  installed-wheel model/license diagnostics before building the handoff wheel.
- Creates a new UTC/revision-named directory and refuses overwrite.
- Writes the wheel, `SHA256SUMS.txt`, and `BUILD-MANIFEST.json` with version, full Git SHA, byte size,
  SHA-256, signing configuration, Authenticode applicability and raw probe status, passed gates, and
  explicit limitations.
- Reports Authenticode as not applicable to the ZIP-based wheel while retaining the raw Windows probe
  result; it does not mistake `UnknownError` for a signature verdict.
- Does not upload, publish, sign, delete, or replace an artifact.

## Verification results

- PowerShell parsing and the full deterministic gate passed: 154 formatted/linted/type-checked
  source files and 773 tests.
- The builder ran from clean pushed revision `14159970faec2c71a7f5c26363e6144aa180231e` after live
  remote-parity verification.
- Isolated installed-wheel diagnostics verified both bundled model assets.
- Independent checks matched the manifest revision, wheel SHA-256, checksum file, schema, and
  signing metadata. The durable evidence record is
  [`docs/evidence/release/2026-07-21.md`](../evidence/release/2026-07-21.md).
