# 2026-07-21 - Installed artifact diagnostics

## Summary

Added safe command-line diagnostics for a source or wheel install. Metadata and integrity checks no
longer require importing the Qt application composition root.

## Commands

- `meyes --version` prints the package version.
- `meyes --diagnose-install` prints JSON covering MEYES/Python/platform versions, both resolved model
  paths, exact sizes, SHA-256 digests, individual verification states, and an overall pass.

## Safety boundary

Both commands use only the Python standard library and the local model-path resolver. They do not
import Qt, start model inference, enumerate/open a camera, construct `SendInput`, or arm Live Input.
The normal no-argument entry point retains the existing desktop startup behavior and Qt arguments.

## Verification

- Seven focused diagnostics/model tests passed.
- Ruff formatting and lint passed across 142 source files, strict mypy passed, and all 745 tests
  passed on native Windows Qt.
- The wheel built and installed without dependencies into isolated Python 3.11.
- `--version` and `--diagnose-install` passed from that wheel; both models resolved from
  `site-packages` with exact size and SHA-256 evidence.
