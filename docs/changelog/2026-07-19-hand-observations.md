# 2026-07-19 — Hand observations

## Summary

Implemented Phase 3A's observation foundation with the official MediaPipe Hand Landmarker model, a replaceable adapter contract, normalized multi-hand observations, and one canonical handedness/mirroring conversion. The adapter emits semantic data only and is not yet connected to gesture or operating-system input paths.

## Added

- Official Google MediaPipe Hand Landmarker `float16/1` model stored locally.
- SHA-256 and exact-size integrity verification for the bundled model.
- `HandObservation`, `DetectedHand`, and anatomical `HandSide` domain models.
- Replaceable hand observation backend and factory protocols.
- MediaPipe `VIDEO`-mode adapter for up to two hands with monotonic timestamps.
- Normalized 21-point landmark tuples in canonical, unmirrored processing coordinates.
- Explicit unknown-handedness handling instead of guessing a side.
- Unit tests for empty results, raw camera input, mirrored input, label correction, coordinate correction, and incomplete results.

## Changed

- Model path resolution now supports `MEYES_HAND_LANDMARKER_MODEL` for explicit local overrides.
- Model asset attribution now records the Hand Landmarker download source, size, digest, and local-only runtime use.
- Updated README, root changelog, and Phase 3 TODO progress.

## Coordinate contract

- Meyes domain landmarks always use unmirrored processing coordinates.
- Meyes hand sides always mean the user's anatomical left or right hand.
- Raw camera input keeps its landmark coordinates and swaps MediaPipe's selfie-oriented handedness label.
- Mirrored input keeps MediaPipe's handedness label and converts `x` back with `1 - x`.
- Preview mirroring remains UI-only and cannot alter this contract.

## Verification

```powershell
.\scripts\check.ps1
```

Results:

- Ruff formatting: passed, 53 files checked.
- Ruff lint: passed.
- mypy strict: passed, 53 source files checked.
- pytest: 45 passed.
- Native MediaPipe model smoke test: passed on a synthetic 640 × 480 frame in about 31 ms.

Critical assertions:

- The 7,819,105-byte model matches SHA-256 `FBC2A30080C3C557093B5DDFC334698132EB341044CCEE322CCF8BCF3607CDE1`.
- Raw, unmirrored input swaps only the selfie-oriented handedness label.
- Mirrored input converts landmark `x` while preserving the anatomical label.
- Missing or unknown classifications remain `UNKNOWN`.
- No camera frame is stored or transmitted.

## Known limitations

- Hand inference is not yet connected to the live vision controller.
- The lower hand-inference cadence and performance budget are not yet implemented.
- Temple anchors and face-width-normalized distance are not yet calculated.
- Bindings and Windows input remain intentionally disconnected.

## Next task

Implement Phase 3B: run hand inference at a lower independent cadence, pair fresh face and hand observations, calculate face temple anchors and face-width-normalized proximity, and cover wrong-hand and stale-observation cases without emitting OS input.
