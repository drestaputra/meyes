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
  SHA-256, Authenticode status, passed gates, and explicit limitations.
- Does not upload, publish, sign, delete, or replace an artifact.

## Verification plan

- Validate every PowerShell script with the parser.
- Run the builder to an isolated temporary output root from a clean pushed revision.
- Parse the manifest and independently match its SHA-256 to the wheel.
