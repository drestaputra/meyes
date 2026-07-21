# 2026-07-20 - Pointer display provenance guard

## Summary

Bound real pointer execution to the exact physical primary-display geometry used by the active
accepted-calibration pipeline. Every pointer movement now re-reads native geometry and fails closed
if the display changed or cannot be verified.

## Added

- Active provisioned-geometry ownership in `CursorPipelineProvisioner`.
- A read boundary that compares current native geometry with the active pipeline geometry.
- Pipeline invalidation with a sanitized recalibration message on mismatch.
- Composition-root wiring that gives the default Windows executor this guarded provider.
- Regression coverage for absent provisioning, matching display, display mismatch, native read
  failure, per-movement reads, and default-executor wiring.

## Safety behavior

- A display mismatch sends no pointer packet for the rejected candidate.
- Mismatch/native read failure removes the candidate pipeline.
- The executor exception reaches the existing Live Input containment path, which faults dispatch,
  releases owned input, and requests camera tracking pause.
- Custom injected executor factories remain available for deterministic tests and do not touch the
  native boundary.

## Verification

Focused Ruff format/lint, strict mypy, and `63 passed` completed first. The full gate then passed:
Ruff format and lint, strict mypy across 138 source files, and `724 passed`.

## Next task

Run the complete deterministic gate, then collect native Windows scaling-matrix and physical reach
evidence without weakening exact consent or display provenance.
