# 2026-07-21 - Wheel model bundling

## Summary

Closed a packaging gap where a built wheel contained the Python package but not the two required
local MediaPipe task bundles. The resolver now supports both installed wheels and source checkouts
without adding a network fallback.

## Changes

- Force-include the complete verified `resources/models` directory under the wheel's `meyes`
  package.
- Bundle the Apache-2.0 license text and third-party notice beside the packaged provenance, and
  require all five artifact entries during verification.
- Prefer packaged model assets, fall back to the source-tree layout, and retain explicit local
  environment overrides.
- Report every attempted local path when an asset is absent.
- Add unit coverage for packaged-first and source-fallback selection.
- Add a fail-fast wheel verifier that builds in a unique temporary directory, inspects required
  archive entries, installs without dependencies into isolated Python 3.11, verifies exact model
  size/checksum through the installed resolver, and safely cleans only its own artifact directory.
- Include wheel verification in the one-command judge gate.

## Verification

- Focused resolver/integrity tests passed.
- Ruff formatting, Ruff lint, strict mypy, and all 742 tests passed on native Windows Qt.
- The wheel built and its archive contained both models, provenance, Apache-2.0 text, and the
  third-party notice.
- An isolated Python 3.11 installation resolved both models from `site-packages` with exact sizes
  and SHA-256 digests.

No standalone Windows executable or installer is claimed by this iteration.
