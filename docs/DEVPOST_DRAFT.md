# MEYES Devpost draft

Human review is required before any text from this file is submitted. Keep the final description,
video, repository revision, and demonstrated behavior consistent.

## Recommended category

Apps for Your Life

## Project name

MEYES

## Tagline

Local, safety-first hands-free Windows control with an ordinary webcam.

## Short description

MEYES is a Windows-first assistive productivity prototype that turns local webcam observations into
gaze pointer candidates, wink clicks, and temple gestures. It starts with operating-system input
disconnected, keeps frames on device, and requires explicit per-session modal consent plus an emergency
shortcut before any real Windows input can be sent.

## Full description

### Inspiration

Many everyday computer tasks assume reliable mouse and keyboard use. MEYES explores a lower-cost,
software-only interaction path using hardware people already have: a Windows computer and an
ordinary webcam. It is an assistive productivity prototype, not a medical device.

### What it does

MEYES runs local face and hand landmark inference, derives normalized binocular gaze features,
detects deliberate left/right winks, and classifies fingertip-to-temple taps and holds. A hands-free
Smooth Pursuit calibration target moves across nine broad screen regions while MEYES pairs webcam
features with its capture-time position, checks target-following correlation, fits a robust
quadratic gaze mapper, and shows held-out metrics. Only fits accepted by a complete configured
evidence policy can provision cursor candidates.

Safe Mode is the default. Diagnostics and a fake action trace let users inspect behavior without OS
output. On Windows, users use a cancel-default safety dialog to arm validated clicks, scrolling,
shortcuts, and—when an accepted display-matched calibration exists—gaze pointer movement through
`SendInput`. `Ctrl+Alt+Shift+F11`, camera loss, profile changes, faults, and shutdown gate output and
release state owned by MEYES. Camera startup never auto-arms real input.

A non-capturing first-run orientation explains the boundary before recording explicit completion.
Dedicated Sensitivity and Camera views apply validated settings only through disarm-first/stopped
lifecycle gates, while Privacy exposes the local data boundary and file locations. When supported,
the system tray mirrors state and offers bounded lifecycle controls without hidden close-to-tray.

Calibration evidence is local, checksummed, policy-bound, and tied to physical display geometry.
Replacement, recoverable forget, restore, and permanent backup deletion use separate cancel-default
confirmation dialogs.
Raw frames, landmarks, gaze samples, and Live Input consent are not persisted.

### How we built it

The application is a typed Python 3.11 and PySide6 desktop app. OpenCV owns camera capture;
MediaPipe face and hand task models run local inference; NumPy supports calibration math; Pydantic
validates configuration; and a narrow ctypes boundary implements Windows DPI/monitor reads,
emergency hotkey registration, physical-input preflight, and `SendInput`.

Codex with GPT-5.6 was the implementation partner for planning, architecture, code generation,
adversarial lifecycle review, deterministic tests, native visual QA, and submission documentation.
The human entrant chose the product direction, local-first boundary, safety model, gesture
vocabulary, acceptance policy, and final tradeoffs. Unsquashed dated commits preserve the build
timeline; commit `57e08f2` is the first explicit post-model-switch GPT-5.6 iteration.

### Challenges

- keeping camera, face, and lower-cadence hand pipelines responsive without stale observations;
- separating semantic gestures and cursor candidates from the real Windows executor;
- containing partial native sends and guaranteeing release-first fault recovery;
- mapping logical calibration targets to physical pixels under Windows DPI virtualization;
- avoiding unsupported accuracy claims before physical evidence exists.

### Accomplishments

- a coherent native workflow from camera diagnostics through calibration and guarded real input;
- explicit, volatile modal consent with a global emergency shortcut and fail-closed lifecycle gates;
- accepted-calibration persistence with checksum, policy, display provenance, recovery, and explicit
  replacement/deletion controls;
- per-movement display-provenance revalidation before absolute pointer packets;
- Safe Mode first-run orientation plus validated Camera/Sensitivity, Privacy, keyboard navigation,
  High Contrast system-theme fallback, and availability-gated tray controls;
- a deterministic pytest suite plus strict mypy and Ruff gates, reproducible at the exact submitted
  revision through the local submission preflight.

### What we learned

For assistive input, the safety boundary is part of the product—not a final polish step. Separating
observations, semantic intent, candidate mapping, consent, and native execution made failure cases
testable and prevented calibration recovery or camera startup from silently enabling OS control.

### What's next

Complete native 125% and 150% scaling evidence, broad physical reach measurement, clean-machine
testing, enabled High Contrast and end-to-end keyboard QA, and packaged Windows delivery. No
universal accuracy threshold is claimed yet.

## Built With

- Python 3.11
- PySide6 / Qt
- OpenCV
- MediaPipe
- NumPy
- Pydantic
- Windows User32 (`SendInput`, hotkeys, DPI and monitor APIs)
- uv
- Ruff, mypy, pytest
- Codex and GPT-5.6 (development workflow; not runtime dependencies)

## Repository and testing

- Repository: `https://github.com/drestaputra/meyes`
- Judge setup and test path: `JUDGES.md`
- Privacy and data boundary: `PRIVACY.md`
- License: MIT, with third-party notices in `THIRD_PARTY_NOTICES.md`

Confirm public visibility or both required private-repository judge invitations before submission.

## Demo script (target 2:35)

### 0:00-0:15 — Problem and promise

Show MEYES opening in `SAFE MODE`. Say: “MEYES explores local hands-free Windows interaction with
an ordinary webcam. It is an assistive productivity prototype, not a medical device.”

### 0:15-0:45 — Local vision diagnostics

Start the camera. Show face/eye diagnostics, a deliberate wink, then a temple tap/hold. State that
frames are processed locally and are not intentionally stored or uploaded.

### 0:45-1:15 — Calibration honesty

Show the full-screen Smooth Pursuit target moving through the screen, live following feedback, and
held-out metrics. If no evidence-backed policy is prepared, show `Review Required` and say pointer
activation remains unavailable. Never present a rejected or review-required fit as accepted.

### 1:15-1:50 — Explicit real input

Open a disposable target, show the Live Input checklist, confirm the arm dialog, and demo one
wink click and one bounded temple scroll. If and only if an accepted, display-matched calibration is
already available, also show gaze movement. Press `Ctrl+Alt+Shift+F11` and show return to Safe Mode.

### 1:50-2:15 — Engineering evidence

Show the test command/result, unsquashed commit history, 100% display evidence, and the separation
between cursor candidates and the guarded executor. Do not claim pending 125%/150% or broad-reach
evidence.

### 2:15-2:35 — Codex and GPT-5.6

Explain the human decisions and how Codex with GPT-5.6 accelerated implementation, safety review,
tests, and native QA. End with the specific audience and next evidence milestones.

## Final human checklist

- Replace the test count/revision with the exact submitted commit.
- Keep the final video below 3:00 and publicly visible on YouTube.
- Use English audio, captions, or an English translation.
- Remove notifications, private data, bystanders, unlicensed music, and unauthorized marks.
- Add the `/feedback` Session ID from the primary project task.
- Confirm entrant eligibility, category, rights, repository access, and final `Submitted` state.
