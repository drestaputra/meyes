# 2026-07-19 — Camera dashboard

## Summary

Completed the Phase 1 camera vertical slice by connecting the tested camera core to the PySide6 dashboard. Device discovery stays off the UI thread, raw frames remain in processing coordinates, preview mirroring happens only during Qt image conversion, and all camera resources are stopped during window shutdown.

## Added

- Qt camera controller with typed object-signal validation.
- Asynchronous bounded device discovery.
- Camera selector with persisted selected index.
- Mirror-preview preference with persisted state.
- Timer-driven latest-frame preview capped near 15 FPS by default.
- Separate capture and preview FPS indicators.
- Textual lifecycle and error status.
- Start, pause, resume, and stop controls with state-dependent availability.
- Responsive preview scaling that preserves aspect ratio.
- Window-close shutdown of capture and device-enumeration work.
- Qt tests for device discovery, mirrored preview, settings signals, camera switching, and persisted automatic selection.

## Changed

- Replaced the static dashboard placeholder with the functional camera control surface.
- Refined QSS so child labels stay transparent while semantic surfaces retain named background tokens.
- Added clear disabled states for primary and secondary controls.
- Updated README, root changelog, and Phase 1 TODO status.

## Verification

Automated commands:

```powershell
.\scripts\check.ps1
```

Results after the complete iteration:

- Ruff formatting: passed, 30 files checked.
- Ruff lint: passed.
- mypy strict: passed, 30 source files checked.
- pytest: 21 passed.

Native visual QA:

- Rendered the 1200×760 dashboard through the Windows Qt platform.
- Verified information hierarchy, transparent labels, semantic surfaces, focus outline, and disabled control styling.
- Confirmed offscreen Qt exposes no system fonts on this machine, so native-platform rendering is the valid visual baseline.

Physical camera smoke:

```text
Detected devices: 1
OpenCV frames read: 20/20
Frame shape: 480 x 640 x 3
Qt preview frames received: 8
Controller state before shutdown: running
Controller state after shutdown: stopped
```

No frames were saved or uploaded during physical camera tests.

## Known limitations

- OpenCV index probing provides generic names such as `Camera 1`; friendly Windows device names are not yet resolved.
- Refresh probes indexes 0–7 and OpenCV may log harmless DirectShow warnings for missing indexes.
- Resolution and target FPS are configured in JSON but do not yet have dashboard editing controls.
- Camera preview is ready, but face/eye inference is intentionally absent until Phase 2.
- The top-level tracking action remains disabled because gesture tracking does not exist yet.

## Next task

Begin Phase 2 with a MediaPipe Face Landmarker adapter, normalized face/eye observations, independent eye-openness diagnostics, and a deterministic wink state machine. Keep OS input disabled throughout Phase 2.
