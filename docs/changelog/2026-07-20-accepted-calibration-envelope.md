# 2026-07-20 - Accepted calibration envelope

## Summary

Added a disconnected repository for accepted quadratic mapper coefficients and their validation
evidence. The repository can persist and recover a proof-carrying `AcceptedCalibration`, but no
runtime controller calls it yet and recovery cannot arm Live Input or produce pointer output.

## Added

- Schema-versioned JSON containing mapper coefficients, holdout metrics, and exact acceptance policy.
- Canonical payload serialization with a SHA-256 corruption-detection checksum.
- A 64 KiB read bound, duplicate-key rejection, strict key sets, finite-number checks, and exact
  coefficient dimensions.
- Atomic temporary-file replacement with flush/fsync and cleanup on failure.
- Recoverable timestamped quarantine for malformed regular files.
- Refusal to follow or quarantine calibration-file links and Windows reparse points.

## Safety decisions

- Save re-evaluates evidence under the supplied policy instead of trusting the token label alone.
- Recovery requires an explicitly configured policy identical to the policy stored at acceptance.
- Recovered evidence is re-evaluated before a new `AcceptedCalibration` token is created.
- No raw gaze samples, capture timestamps, frames, landmarks, or source sequences are stored.
- SHA-256 detects corruption but is explicitly not described as authentication against a local
  attacker.
- This iteration does not wire save, startup recovery, pipeline provisioning, or any executor.

## Verification

Focused Ruff and strict mypy passed; 12 persistence tests passed in 0.81 seconds.

Full repository gate:

- Ruff format: 136 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 136 source files.
- Native Windows pytest: 686 passed in 19.14 seconds.

## Known limitations

- Users cannot yet explicitly save, replace, delete, or recover an accepted calibration through UI.
- Runtime lifecycle and configuration-change invalidation remain pending.
- Evidence-backed acceptance defaults and physical-device scaling QA remain pending.

## Next task

Add an explicit persistence lifecycle controller that saves only a newly accepted volatile fit,
recovers only at safe startup, clears provisioning before replacement, and never alters Live Input
consent or arming state.
