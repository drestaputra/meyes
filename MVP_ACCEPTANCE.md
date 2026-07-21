# MEYES MVP acceptance checklist

Status: source candidate - not an accepted standalone MVP release.

This checklist maps the current repository to `DEVELOPMENT_PLAN.md`. It deliberately separates
deterministic evidence from human/hardware, delivery, and external submission work. A checked source
item does not satisfy a pending live or external row.

Status vocabulary:

- **PASS** - the named evidence exists and was verified within its stated scope;
- **PARTIAL** - substantial evidence exists, but a required environment or human path remains;
- **BLOCKED** - release acceptance cannot be claimed until an external/human dependency is complete;
- **DEFERRED** - outside the current MVP rather than silently missing.

## Current automated baseline

| Gate | Current evidence | Status |
|---|---|---|
| Frozen source quality | Ruff format/lint, strict mypy, and 787 tests passed across 158 source files on the packaged-icon iteration. | PASS |
| Exact remote parity | `scripts/submission_preflight.ps1 -VerifyRemote` passed on `main` after every completed iteration. | PASS |
| Remote Windows quality | Pinned workflow run `29848753863` passed documentation, Ruff, strict mypy, all 787 tests, and isolated installed-wheel integrity on revision `c91c3a1`. | PASS within managed-runner scope |
| Installed artifact integrity | Isolated wheel installation resolved and verified both packaged models plus licenses/notices. | PASS |
| Release artifact integrity | Exact-revision wheel, manifest, checksum file, and independent SHA-256/revision assertions are recorded in `docs/evidence/release/2026-07-21.md`. | PASS |
| Synthetic performance boundary | Real model adapters completed the bounded blank-frame probe; results and the no-optimization decision are in `docs/evidence/performance/2026-07-21.md`. | PASS within synthetic scope |

Run the current deterministic baseline with:

```powershell
.\scripts\judge_verify.ps1
```

It does not open a camera or arm operating-system input.

## Product acceptance matrix

| Area | Evidence present | Required before release acceptance | Status |
|---|---|---|---|
| Configuration and recovery | Typed schema, atomic writes, corrupt-file backup/default recovery, profile and calibration lifecycle tests. | Clean-user recovery smoke on a supported clean machine. | PARTIAL |
| Camera lifecycle | Fake-backend discovery/start/pause/resume/stop/recovery/shutdown tests; native Dashboard and settings layouts. | Representative physical camera permission, disconnect/reconnect, requested-mode negotiation, and shutdown pass. | PARTIAL |
| Face/wink pipeline | Packaged Face Landmarker integrity, normalized observations, independent wink/blink suppression, freshness and fixture tests. | Representative live lighting, glasses/occlusion, movement, and false-positive observations. | PARTIAL |
| Hand/temple pipeline | Packaged Hand Landmarker integrity, canonical handedness, lower cadence, proximity hysteresis, tap/hold/timeout tests. | Live wrong-hand, both-hands, loss-during-hold, field-of-view, and recovery evidence. | PARTIAL |
| Bindings and profiles | Validated actions, all six gesture bindings, fake executor/trace, guarded profile lifecycle and transfer, no-JSON editors. | Human keyboard/file-dialog pass on a clean user profile. | PARTIAL |
| Windows native input | `SendInput` serialization/partial-send/reverse-release tests, exact consent, hotkey/physical-input/release-first gates, fail-closed lifecycle wiring. | Disposable-target live safety pass, including emergency chord and higher-integrity/UIPI limitation; never required for ordinary Safe Mode review. | PARTIAL |
| Calibration and gaze pointer | Nine-point bounded collection, robust fit/holdout metrics, all-or-none acceptance, checksummed policy/display-bound persistence, adaptive smoothing/gates, per-move display validation. | Representative physical-device thresholds plus broad screen reach; default remains `Review Required` until justified. | PARTIAL |
| UI and accessibility | All nine views implemented; top/bottom native 900×640 and top 1200×760 review; no horizontal overflow; keyboard shell shortcuts/focus tests; textual non-color safety state. | Human full-screen calibration/native-dialog keyboard pass, 125%/150% scale, and enabled High Contrast visual/keyboard evidence. | PARTIAL |
| Privacy and recovery copy | `PRIVACY.md`, read-only Privacy view, `TROUBLESHOOTING.md`, local paths, deletion/recovery boundaries, no intentional frame persistence. | Review on the exact shipped package and dependency versions. | PASS for source candidate |
| Performance | Latest-frame buffers, independent workers, 10 FPS hand cadence, synthetic exact-revision profile, no unsupported optimization. | Live detected-face/hand, preview latency, CPU/memory, sustained thermal/load measurements on representative devices. | PARTIAL |
| Windows delivery | Verified Python wheel with bundled models, diagnostics, manifest, checksum, signing requirements, plus a recorded packager/toolchain readiness spike. | Provision an isolated compiler/Nuitka environment; select from measured builds; create standalone delivery/resources/recovery; sign when authorized; clean-machine install/launch/uninstall. | BLOCKED |

## Safety invariants required on every future build

- Startup and camera start keep OS input disconnected.
- Live Input consent is exact, volatile, per session, and never restored.
- Emergency registration, clear physical inputs, and release-first initialization must all pass
  before native output is armed.
- Camera pause/stop/fault, tracking loss, profile/calibration/file-dialog transitions, display
  mismatch, executor fault, emergency activation, and shutdown gate/release owned input.
- Pointer movement requires an accepted current-policy calibration whose exact physical primary
  display is revalidated before every native move.
- Raw frames are bounded in memory and are not intentionally stored or uploaded.
- No release or demo may invent accuracy, latency, reach, accessibility, privacy-certification, or
  performance claims.

The deterministic tests cover these boundaries without granting permission to skip the live release
checks above.

## Build Week external acceptance

These are not repository automation tasks and remain **BLOCKED** until completed by the entrant:

- eligibility, ownership, rights, country/submitter type, category, and team attestations;
- public repository access or both required private judge invitations;
- a human-approved English project name/tagline/description/Built With/testing path;
- public sub-three-minute YouTube demo plus privacy/rights review;
- the primary Codex task `/feedback` Session ID;
- an authenticated Devpost project whose final state is **Submitted**, not Draft;
- continued free repository/video/testing access through the required judging period.

Use `docs/TODO.md` and `docs/BUILD_WEEK_SUBMISSION.md` for the exact open external checklist. Local
preflight can report these blockers but cannot attest or submit them.

## Release decision

- **Source candidate:** ready for deterministic judge verification.
- **Build Week repository evidence:** ready within documented source/wheel scope.
- **Standalone MVP release:** **NOT ACCEPTED** - delivery selection, clean-machine packaging, and the
  human/hardware rows above remain incomplete.
- **Devpost submission:** **NOT ASSERTED** - entrant actions remain external.

Do not change these final two statuses to accepted/complete merely because the deadline is near.
