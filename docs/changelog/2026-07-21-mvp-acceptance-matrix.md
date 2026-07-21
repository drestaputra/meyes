# 2026-07-21 - MVP acceptance matrix

## Summary

Added one evidence-mapped release checklist that prevents deterministic source success from being
mistaken for live hardware, standalone delivery, or external Devpost completion.

## Coverage

- Current frozen quality, remote-parity, installed-wheel, release checksum, and synthetic
  performance evidence.
- Product rows for config, camera, face/wink, hand/temple, bindings/profiles, native input,
  calibration/pointer, UI/accessibility, privacy/recovery, performance, and Windows delivery.
- Safety invariants that every future build must retain.
- Human/hardware, packager/signing, and Build Week external blockers.
- Explicit final decisions: source candidate ready; standalone MVP and Devpost submission not
  asserted complete.

## Verification

- Cross-checked the matrix against `DEVELOPMENT_PLAN.md`, `docs/TODO.md`, `JUDGES.md`, current
  evidence records, and the submission readiness document.
- No pending human/hardware or external item was converted into a passing claim.
