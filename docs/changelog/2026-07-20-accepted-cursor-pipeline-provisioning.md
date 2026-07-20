# 2026-07-20 - Accepted cursor pipeline provisioning

## Summary

Connected volatile accepted calibration and validated Windows primary-screen geometry to the
production fake-only cursor diagnostics pipeline. The connection remains structurally unable to
send operating-system input because neither the provisioner nor the pipeline accepts an executor.

## Added

- A `PhysicalScreenGeometryProvider` protocol independent of the Windows ctypes implementation.
- A typed provisioning result distinguishing unavailable, ready, and native-fault outcomes.
- Automatic `MainWindow` synchronization from calibration fit changes.
- Persistent unavailable reasons in cursor diagnostics across camera start transitions.
- Tests for acceptance gating, candidate construction, unsupported platforms, and native faults.

## Safety decisions

- Geometry is never read before an `AcceptedCalibration` token exists.
- Starting, cancelling, or replacing calibration removes and resets the prior pipeline immediately.
- A native geometry fault removes any existing pipeline and clears the last pixel candidate.
- No fallback screen dimensions, review-required bypass, or persisted calibration is used.
- The configured pipeline has no `InputExecutor`; `SendInput` pointer movement remains disconnected.

## Verification

Focused Ruff and strict mypy passed; 21 provisioning, diagnostics, and `MainWindow` tests passed in
4.58 seconds.

Full repository gate:

- Ruff format: 134 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 134 source files.
- Native Windows pytest: 674 passed in 17.89 seconds.

## Known limitations

- The default acceptance policy remains intentionally unset, so ordinary production startup remains
  unavailable until evidence-backed thresholds are explicitly configured and passed.
- Accepted calibration is volatile and is not recovered across launches.
- Scaling-matrix physical-device QA and all gaze pointer output remain pending.

## Next task

Define a versioned, integrity-checked persistence envelope for accepted calibration evidence and
mapper coefficients, with fail-closed recovery that cannot arm Live Input or pointer output.
