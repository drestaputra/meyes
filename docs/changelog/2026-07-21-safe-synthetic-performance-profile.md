# 2026-07-21 - Safe synthetic performance profile

## Summary

Added a repeatable JSON performance probe for the real packaged Face and Hand Landmarker adapters
without opening a camera, importing Qt, registering a hotkey, or constructing native input.

## Behavior

- Uses one bounded 640×480 all-zero in-memory BGR frame for 12 sequential iterations per adapter.
- Separately records initialization, first inference, warm median/p95/max, and close timing.
- Discards two explicit warmup iterations from warm statistics.
- Closes each initialized backend even when processing fails and returns nonzero if either adapter
  cannot complete all iterations.
- Labels results as host/load/runtime/dependency-specific synthetic evidence, not live accuracy,
  latency, or throughput.
- Notes that production initializes the adapters on separate workers and that MediaPipe dependency
  network behavior remains governed by `PRIVACY.md`.
- Provides `scripts/profile_safe.ps1` through the existing direct-uv/`python -m uv` frozen launcher.

## Verification

- Unit coverage includes bounded success, exact synthetic shape/content, cleanup on failure,
  parameter validation, and a CLI route that cannot fall through to the desktop application.
- Focused Ruff, strict mypy, 11 focused tests, PowerShell parsing, and a real local adapter run passed.
- The first real run showed a substantially larger Face Landmarker cold initialization than warm
  blank-frame inference. Production already performs initialization in a worker thread, so no
  unmeasured architectural optimization was introduced.

## Next evidence step

Run the probe again from a clean pushed revision, record the exact host-specific result, then keep
live-camera and real detected-face/hand performance explicitly pending.
