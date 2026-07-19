# 2026-07-19 — Temple proximity features

## Summary

Implemented the pure Phase 3 temple-feature layer. It pairs each lower-cadence hand observation with the best fresh face frame, calculates same-side anatomical index-fingertip proximity in pixel-corrected coordinates, and normalizes the result by measured face width. It produces features and explicit unavailable states only; no gesture or operating-system action is emitted.

## Added

- Actual frame width and height on normalized face and hand observations.
- Bounded face-history tracker with same-sequence preference and nearest-capture fallback.
- Independent maximum pair-skew and maximum observation-age gates.
- Anatomical temple anchors inferred from symmetric MediaPipe face-oval topology:
  - right temple: mean of landmarks 127 and 162;
  - left temple: mean of landmarks 356 and 389.
- Face-width baseline between landmarks 234 and 454.
- Same-side index-fingertip feature using Hand Landmark 8.
- Pixel-space XY distance correction before face-width normalization.
- Explicit feature statuses for ready, no eligible hand, face loss, stale hand, unavailable face, pair skew, invalid geometry/time, out-of-order input, and expiry.
- Watchdog-ready `expire()` and full lifecycle `reset()` APIs.
- Twenty-six deterministic geometry, freshness, ordering, and failure tests.

## Changed

- MediaPipe adapters now copy negotiated frame dimensions from every source packet.
- Duplicate same-side hands select highest handedness confidence, then nearest same-side temple, with stable coordinate tie-breaks.
- A paired feature expires when its oldest input reaches the tracking timeout, not merely when the newer hand frame ages out.
- Expiry emits the current monotonic timestamp so a later state machine can always process the timeout transition.
- Updated README, root changelog, and Phase 3 TODO progress.

## Geometry contract

```text
pixel(point) = (point.x × frame_width, point.y × frame_height)
face_width = distance(pixel(face[234]), pixel(face[454]))
distance_ratio = distance(pixel(hand[8]), pixel(temple_anchor)) / face_width
```

- All coordinates are already canonical and unmirrored before extraction.
- Left hands are measured only against the anatomical left temple; right hands only against right.
- Unknown sides are ignored and never inferred from screen position.
- Z is intentionally excluded because face and hand models do not share a common 3D origin.
- Face width below one pixel, mismatched frame dimensions, missing landmarks, or non-finite data fail closed.
- Anchor naming is an anatomical inference from the [official FaceMesh topology](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/python/solutions/face_mesh_connections.py); MediaPipe does not publish a landmark explicitly named “temple.”

## Verification

```powershell
.\scripts\check.ps1
```

Expected results for this iteration:

- Ruff formatting: passed, 58 files checked.
- Ruff lint: passed.
- mypy strict: passed, 58 source files checked.
- pytest: 82 passed.
- Focused temple feature suite: 26 passed.

Critical assertions:

- A 38.4-pixel horizontal or vertical fingertip offset on the 640 × 480 fixture produces the same `0.1` ratio.
- A left hand placed at the right temple remains a left-side feature with ratio `1.0`; it is never remapped.
- Same-confidence duplicate detections are order independent.
- Pairing uses capture time rather than delayed processing time.
- Future, stale, non-finite, regressing, and duplicate timestamps fail closed.
- A face older than its paired hand expires the pair as soon as the face reaches the timeout.
- Expiry occurs without requiring another camera observation.

## Known limitations

- Hand worker output is not yet composed into the live Qt controller.
- `expire()` is ready but does not yet have a Qt watchdog caller.
- Feature delivery ordering across face, hand, and watchdog callbacks will be serialized during controller composition.
- Confidence thresholds, palm plausibility, proximity hysteresis, stabilization, tap, and hold states remain intentionally deferred.
- Bindings and Windows input remain intentionally disconnected.

## Next task

Compose face and hand workers in the Qt vision controller, derive feature freshness from `GestureSettings.tracking_timeout_ms`, add a serialized watchdog, expose live hand/temple diagnostics, and verify the physical camera-to-both-model pipeline without OS input.
