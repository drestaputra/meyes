# MEYES — Codex Implementation Specification

> **Working title:** MEYES  
> **Product type:** Windows desktop accessibility and productivity application  
> **Primary interaction:** Control the mouse pointer using eye gaze, trigger mouse clicks using independent eye gestures, and scroll or execute shortcuts using hand-to-temple gestures.

---

## 1. Instructions for Codex

Build this project incrementally as a working Windows desktop application.

Rules:

1. Use the architecture, interfaces, and directory structure defined in this document.
2. Prioritize a stable MVP over advanced gaze-model accuracy.
3. Do not tightly couple computer-vision detection to operating-system input execution.
4. Every gesture must pass through a state machine and configurable binding layer.
5. The application must remain usable when hand tracking is temporarily lost.
6. All camera processing must remain local. Do not upload frames or biometric data.
7. Add type hints, structured logging, error handling, and tests for non-vision logic.
8. Avoid premature migration to Rust or C++. Optimize only after profiling.
9. Implement Windows first. Keep OS-specific code behind an interface.
10. At the end of each implementation phase:
    - run tests;
    - run static checks;
    - summarize changed files;
    - list remaining limitations;
    - update `CHANGELOG.md`.

The first deliverable must be a runnable MVP, not only scaffolding.

---

## 2. Product Summary

MEYES is a hands-free mouse-control application that uses a standard webcam.

Default controls:

| Gesture | Default action |
|---|---|
| Eye gaze | Move mouse pointer |
| Left-eye wink | Left click |
| Right-eye wink | Right click |
| Tap right temple | Scroll up |
| Hold right temple | Continuous scroll up |
| Tap left temple | Scroll down |
| Hold left temple | Continuous scroll down |
| Release temple | Stop continuous action |
| Emergency keyboard shortcut | Pause or resume tracking |

All gesture bindings must be customizable. A user may replace any default action with a mouse action, keyboard key, keyboard shortcut, or disabled state.

The system does not need to prove physical skin contact. A temple-touch gesture is defined as a stable fingertip position sufficiently close to the configured temple region.

---

## 3. Product Goals

### 3.1 MVP goals

- Move the Windows cursor using estimated gaze from a webcam.
- Calibrate gaze using a guided multi-point calibration screen.
- Detect independent left-eye and right-eye winks.
- Detect left-hand-to-left-temple and right-hand-to-right-temple proximity.
- Distinguish temple tap from temple hold.
- Execute configurable mouse and keyboard actions.
- Provide a native settings interface.
- Run in the Windows system tray.
- Allow tracking to be paused immediately.
- Persist settings and calibration locally.
- Package the application as a Windows executable.

### 3.2 Quality goals

- Responsive enough for normal desktop navigation.
- No repeated click from one sustained wink.
- No endless scroll after hand tracking is lost.
- UI remains responsive while vision inference is running.
- Camera failure produces a recoverable error, not an application crash.
- Default configuration is safe and understandable.
- User can restore default bindings.

### 3.3 Non-goals for the first MVP

- Medical-device certification.
- Guaranteed accessibility for every disability profile.
- Mobile operating systems.
- macOS and Linux input backends.
- Cloud synchronization.
- User accounts.
- Remote telemetry.
- Raw command or arbitrary script execution.
- Multi-camera fusion.
- Dedicated infrared eye-tracker hardware.
- Perfect pixel-level gaze accuracy from an ordinary webcam.

---

## 4. Naming

### 4.1 Recommended working name

**MEYES**

Interpretation:

- “my eyes”;
- eyes acting as a mouse;
- short and easy to place in an icon or tray label.

### 4.2 Other candidates

| Name | Assessment |
|---|---|
| MEYES | Best working name; directly associated with eyes |
| MICES | Memorable but sounds like the plural of “mouse” |
| MEYSE | More distinctive blend of “mouse” and “eyes”, but pronunciation is less obvious |
| GazeTap | Descriptive, especially for gaze plus gestures |
| IrisPilot | Sounds polished but may imply iris-specific hardware |
| LookPointer | Very descriptive but less brandable |
| GazeBind | Strong for customizable gesture bindings |
| EyeMotion | Broad and easy to understand |

Use `Meyes` as the package and display name for now. Keep branding isolated so it can be renamed later.

Suggested Python package:

```text
meyes
```

Suggested executable:

```text
Meyes.exe
```

---

## 5. Target Platform

Initial target:

```text
Windows 10 and Windows 11, 64-bit
```

Expected hardware:

- integrated or USB webcam;
- minimum 640×480 video;
- modern dual-core CPU or better;
- 4 GB RAM minimum;
- no dedicated GPU required.

The program must support selecting a camera index from settings.

---

## 6. Technology Stack

### 6.1 Required stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Dependency management | `uv` with `pyproject.toml`, or Poetry if `uv` is unavailable |
| Camera input | OpenCV |
| Face and eye landmarks | MediaPipe Face Landmarker |
| Hand landmarks | MediaPipe Hand Landmarker |
| Numeric operations | NumPy |
| Desktop UI | PySide6 |
| Validation/config models | Pydantic |
| Windows input | Win32 `SendInput` through `ctypes` |
| Local config | JSON |
| Logging | Python `logging` with rotating file handler |
| Tests | pytest |
| Linting | Ruff |
| Type checking | mypy or Pyright |
| Packaging | Nuitka or `pyside6-deploy` |
| Optional future inference | ONNX Runtime |

### 6.2 Avoid for the MVP

- Electron;
- browser-only UI;
- Flutter desktop;
- a local HTTP server;
- microservices;
- database servers;
- direct use of PyAutoGUI as the production input backend;
- running separate face and iris models when Face Landmarker already supplies the required landmarks.

PyAutoGUI may be used only in an early smoke test. Replace it with the Windows input backend before the MVP is considered complete.

---

## 7. High-Level Architecture

```text
Webcam
  |
  v
Camera Capture Worker
  |
  v
Latest-Frame Buffer
  |
  +--------------------------+
  |                          |
  v                          v
Face/Eye Pipeline        Hand Pipeline
  |                          |
  +------------+-------------+
               |
               v
        Observation Model
               |
               v
       Gesture State Machine
               |
               v
         Gesture Events
               |
               v
         Binding Manager
               |
               v
         Action Executor
               |
       +-------+--------+
       |                |
       v                v
Windows Mouse      Windows Keyboard
```

The UI reads application state but must not perform computer-vision inference on the UI thread.

---

## 8. Core Design Principles

### 8.1 Latest frame wins

Do not queue every webcam frame. Use a buffer containing only the most recent frame.

Reason:

- old frames increase latency;
- real-time control values freshness more than complete frame processing.

### 8.2 Separate observations from gestures

Vision pipelines produce observations such as:

```python
FaceObservation(
    timestamp=...,
    face_detected=True,
    gaze_normalized=(0.51, 0.43),
    left_eye_openness=0.18,
    right_eye_openness=0.31,
    left_temple=(0.22, 0.35),
    right_temple=(0.78, 0.35),
    face_width=0.42,
)
```

Hand pipeline produces observations such as:

```python
HandObservation(
    timestamp=...,
    side="right",
    confidence=0.91,
    index_tip=(0.79, 0.36),
    palm_center=(0.87, 0.52),
)
```

Gesture detection consumes these observations and emits semantic events:

```text
LEFT_WINK
RIGHT_WINK
LEFT_TEMPLE_TAP
LEFT_TEMPLE_HOLD_START
LEFT_TEMPLE_HOLD_END
RIGHT_TEMPLE_TAP
RIGHT_TEMPLE_HOLD_START
RIGHT_TEMPLE_HOLD_END
```

### 8.3 Separate gestures from actions

Never implement:

```python
if right_temple_touch:
    scroll_up()
```

Implement:

```python
event = gesture_engine.update(observations)
binding = binding_manager.resolve(event)
action_executor.execute(binding)
```

This enables customization without changing vision code.

### 8.4 Every continuous gesture must have a fail-safe

Continuous scroll must stop when any of these occurs:

- finger leaves the temple region;
- hand observation times out;
- face observation times out;
- camera disconnects;
- tracking is paused;
- application exits;
- emergency-stop shortcut is pressed.

---

## 9. Application Modules

### 9.1 Camera module

Responsibilities:

- enumerate available cameras;
- open selected camera;
- configure resolution and target FPS;
- mirror preview when enabled;
- publish the latest frame;
- reconnect after a temporary failure;
- report health status.

Default:

```json
{
  "camera_index": 0,
  "width": 640,
  "height": 480,
  "target_fps": 30,
  "mirror": true
}
```

Do not assume the camera actually provides the requested FPS. Measure effective FPS.

### 9.2 Face and gaze module

Responsibilities:

- detect one primary face;
- extract eye and iris landmarks;
- estimate eye openness independently;
- determine left and right temple anchor regions;
- estimate normalized gaze;
- provide head-pose features for future compensation;
- expose confidence and timestamps.

For MVP gaze estimation:

1. Calculate iris position relative to each eye bounding region.
2. Combine the two eyes.
3. Apply calibration mapping.
4. Smooth the resulting screen coordinates.
5. Clamp to screen bounds.

Do not begin with a large neural gaze model. Add ONNX-based gaze estimation only after the landmark-based pipeline is functional and measured.

### 9.3 Hand module

Responsibilities:

- detect up to two hands;
- expose index fingertip and palm landmarks;
- expose handedness confidence;
- compensate for mirrored camera preview;
- associate a hand with the correct side of the face.

Run hand inference at a lower frequency than face inference when needed.

Target rates:

```text
Camera capture: 30 FPS
Face inference: 20–30 FPS
Hand inference: 10–15 FPS
UI preview: 10–15 FPS
Cursor updates: up to 60 Hz using latest smoothed gaze
```

### 9.4 Gesture engine

Responsibilities:

- independent wink detection;
- temple proximity detection;
- tap-versus-hold classification;
- debouncing;
- cooldown;
- event emission;
- recovery from lost tracking.

Use monotonic timestamps, not wall-clock time.

### 9.5 Calibration module

Implement a full-screen guided calibration flow.

MVP flow:

1. Explain how the user should sit.
2. Confirm the face is detected.
3. Display nine targets:
   - top-left;
   - top-center;
   - top-right;
   - middle-left;
   - center;
   - middle-right;
   - bottom-left;
   - bottom-center;
   - bottom-right.
4. Gather multiple gaze samples per target.
5. Reject obvious outliers.
6. Fit a mapping from gaze features to normalized screen coordinates.
7. Validate using a second pass.
8. Save calibration profile.

Begin with polynomial regression or another lightweight mapping. Keep the mapping implementation behind an interface so it can later be replaced.

### 9.6 Binding manager

Responsibilities:

- load default bindings;
- load user bindings;
- validate configuration;
- resolve gesture events to actions;
- support reset to defaults;
- support per-profile configurations;
- reject unsafe or unsupported actions.

### 9.7 Input executor

Define a platform-neutral interface:

```python
from typing import Protocol

class InputExecutor(Protocol):
    def move_pointer(self, x: int, y: int) -> None: ...
    def mouse_click(self, button: str) -> None: ...
    def mouse_down(self, button: str) -> None: ...
    def mouse_up(self, button: str) -> None: ...
    def mouse_scroll(self, amount: int) -> None: ...
    def key_down(self, key: str) -> None: ...
    def key_up(self, key: str) -> None: ...
    def keyboard_shortcut(self, keys: list[str]) -> None: ...
    def release_all(self) -> None: ...
```

Implement:

```text
WindowsSendInputExecutor
```

Call `release_all()` during pause, error recovery, and shutdown.

### 9.8 UI module

Required screens:

1. **Dashboard**
   - tracking on/off;
   - face detected;
   - left hand detected;
   - right hand detected;
   - camera FPS;
   - inference FPS;
   - active profile;
   - calibration status.

2. **Calibration**
   - start calibration;
   - recalibrate;
   - validation score;
   - camera positioning guidance.

3. **Bindings**
   - gesture;
   - action;
   - action parameters;
   - tap/hold settings;
   - reset defaults.

4. **Sensitivity**
   - wink threshold;
   - minimum wink duration;
   - gesture cooldown;
   - temple distance threshold;
   - temple stabilization duration;
   - hold threshold;
   - cursor smoothing;
   - scroll step;
   - continuous scroll interval.

5. **Camera**
   - camera selector;
   - resolution;
   - mirror;
   - preview;
   - optional landmark debug overlay.

6. **Profiles**
   - create;
   - duplicate;
   - rename;
   - activate;
   - delete;
   - import/export JSON.

7. **Diagnostics**
   - live eye openness values;
   - live temple distances;
   - tracking confidence;
   - recent gesture-event log;
   - performance metrics.

### 9.9 System tray

Tray menu:

```text
Open Meyes
Pause Tracking
Resume Tracking
Recalibrate
Active Profile >
Exit
```

Closing the main window should minimize to tray unless the user explicitly selects Exit.

---

## 10. Gesture Definitions

### 10.1 Eye gestures

Terminology:

- **wink:** one eye closes while the other remains open;
- **both-eye blink:** both eyes close naturally.

Default behavior:

- left wink triggers left click;
- right wink triggers right click;
- natural both-eye blink triggers no action.

This distinction is critical. Do not trigger clicks when both eyes close at approximately the same time.

Suggested logical conditions:

```text
LEFT_WINK:
left eye closed
AND right eye open
AND state stable for minimum duration

RIGHT_WINK:
right eye closed
AND left eye open
AND state stable for minimum duration
```

Initial configurable values:

```json
{
  "wink_min_duration_ms": 140,
  "wink_max_duration_ms": 900,
  "wink_cooldown_ms": 350,
  "both_eye_sync_window_ms": 90
}
```

Thresholds must be calibrated per user or adjustable.

### 10.2 Temple gestures

Default mapping:

```text
Right temple tap  -> scroll up
Right temple hold -> continuous scroll up
Left temple tap   -> scroll down
Left temple hold  -> continuous scroll down
```

A temple gesture is active only when all conditions pass:

1. correct hand side;
2. index fingertip is near the same-side temple anchor;
3. palm or additional landmarks are in a plausible position;
4. proximity is stable for the configured duration;
5. the observation is recent;
6. confidence is above threshold.

Use face width as the distance scale:

```python
normalized_distance = fingertip_temple_distance / face_width
```

Suggested defaults:

```json
{
  "temple_enter_distance_ratio": 0.075,
  "temple_exit_distance_ratio": 0.095,
  "temple_stabilization_ms": 180,
  "temple_hold_threshold_ms": 550,
  "temple_cooldown_ms": 250,
  "tracking_timeout_ms": 250
}
```

Use different enter and exit thresholds to create hysteresis and reduce flicker.

### 10.3 Tap and hold rules

State sequence:

```text
IDLE
  -> CANDIDATE
  -> PRESSED
  -> HOLDING
  -> RELEASED
  -> COOLDOWN
  -> IDLE
```

Rules:

- `CANDIDATE`: fingertip enters the temple region.
- `PRESSED`: proximity remains stable for the stabilization duration.
- If released before hold threshold:
  - emit `*_TEMPLE_TAP`.
- If duration reaches hold threshold:
  - emit `*_TEMPLE_HOLD_START` once.
- While holding:
  - do not repeatedly emit start events.
- On release or timeout:
  - emit `*_TEMPLE_HOLD_END`.
- Enter cooldown before accepting another gesture.

A tap action must be emitted on release because before release the system cannot know whether the interaction will become a hold.

### 10.4 Handedness and mirroring

MediaPipe handedness may appear reversed depending on whether input frames are mirrored.

Create one canonical coordinate system:

- maintain original processing coordinates;
- separately control whether preview is mirrored;
- convert handedness exactly once;
- add a diagnostics screen to confirm detected left/right hands.

Do not scatter mirror corrections across modules.

---

## 11. Cursor Movement

### 11.1 Mapping

Map calibrated normalized gaze coordinates to the current Windows virtual screen.

Prepare for multiple monitors, but support the primary monitor first.

Interface:

```python
class GazeMapper(Protocol):
    def map_to_screen(
        self,
        gaze_features: "GazeFeatures",
        screen_width: int,
        screen_height: int,
    ) -> tuple[int, int]: ...
```

### 11.2 Smoothing

Use a One Euro Filter or equivalent adaptive smoothing.

Requirements:

- small eye jitter should not shake the cursor;
- rapid intentional movement should remain responsive;
- smoothing parameters are configurable.

Do not use a large fixed moving average that introduces excessive delay.

### 11.3 Cursor freeze during temple gesture

Default behavior:

- freeze gaze-based cursor movement while a temple gesture is confirmed;
- resume after release and a short stabilization period.

Make this configurable:

```json
{
  "freeze_cursor_during_temple_gesture": true,
  "resume_cursor_delay_ms": 120
}
```

### 11.4 Safety behavior

If face confidence falls below threshold:

- hold the pointer at its last position;
- do not jump to screen center;
- suppress click gestures;
- stop continuous actions after timeout.

---

## 12. Action and Binding System

### 12.1 Supported action types for MVP

```text
disabled
mouse_click
mouse_double_click
mouse_down
mouse_up
mouse_scroll
mouse_scroll_continuous
keyboard_key
keyboard_shortcut
pause_tracking
resume_tracking
toggle_tracking
```

Do not support arbitrary shell commands in the MVP.

### 12.2 Default binding configuration

```json
{
  "schema_version": 1,
  "profile_name": "Default",
  "bindings": {
    "LEFT_WINK": {
      "type": "mouse_click",
      "button": "left"
    },
    "RIGHT_WINK": {
      "type": "mouse_click",
      "button": "right"
    },
    "RIGHT_TEMPLE_TAP": {
      "type": "mouse_scroll",
      "amount": 3
    },
    "RIGHT_TEMPLE_HOLD": {
      "type": "mouse_scroll_continuous",
      "amount": 2,
      "interval_ms": 100
    },
    "LEFT_TEMPLE_TAP": {
      "type": "mouse_scroll",
      "amount": -3
    },
    "LEFT_TEMPLE_HOLD": {
      "type": "mouse_scroll_continuous",
      "amount": -2,
      "interval_ms": 100
    }
  }
}
```

Treat the sign convention as an implementation detail. The UI must display human-readable directions.

### 12.3 Keyboard shortcut configuration

Example:

```json
{
  "type": "keyboard_shortcut",
  "keys": ["CTRL", "SHIFT", "TAB"]
}
```

Validate:

- supported key names;
- no duplicate modifier;
- at least one key;
- maximum reasonable shortcut length;
- all pressed keys are released even after an exception.

### 12.4 Binding UI

Each gesture row must show:

```text
Gesture: Right Temple Tap
Action:  Scroll
Direction: Up
Amount: 3
```

For keyboard shortcuts, provide a “Record shortcut” button that captures the next shortcut without triggering the assigned system action when possible.

---

## 13. Configuration

### 13.1 Paths

Use Windows-appropriate local directories.

Suggested locations:

```text
%APPDATA%\Meyes\config.json
%APPDATA%\Meyes\profiles\
%LOCALAPPDATA%\Meyes\logs\
%LOCALAPPDATA%\Meyes\calibration\
```

Create directories safely if missing.

### 13.2 Configuration sections

```json
{
  "schema_version": 1,
  "app": {},
  "camera": {},
  "tracking": {},
  "gestures": {},
  "cursor": {},
  "bindings": {},
  "ui": {},
  "privacy": {}
}
```

Use Pydantic models and migrations for future schema versions.

### 13.3 Corrupt configuration

If a config file is invalid:

1. rename it to a timestamped backup;
2. restore safe defaults;
3. show a non-blocking warning;
4. write details to logs.

Do not crash during startup.

---

## 14. Concurrency Model

Use PySide6 threads or Python worker threads initially.

Recommended workers:

```text
UI/Main thread
Camera worker
Vision worker
Input/action worker
```

Possible refinement:

- face and hand inference may run in one vision worker to avoid excessive synchronization;
- hand inference can be skipped on selected frames;
- cursor output may use latest gaze data at a higher update rate than inference.

Rules:

- never update Qt widgets directly from a worker;
- communicate through signals or thread-safe queues;
- latest-frame queue size must be one;
- action queue may be bounded;
- shutdown must be deterministic;
- workers must stop before camera resources are released.

Move vision to a separate process only if profiling shows that threads cause unacceptable UI latency.

---

## 15. Performance Requirements

Targets for the MVP on a typical modern Windows laptop:

| Metric | Target |
|---|---|
| Camera resolution | 640×480 default |
| Effective capture rate | 24 FPS or higher where hardware supports it |
| Face inference | 20 FPS or higher |
| Hand inference | 10 FPS or higher |
| UI responsiveness | No visible freeze during inference |
| Gesture-to-action latency | Preferably below 150 ms after gesture confirmation |
| Continuous action stop | Within tracking timeout after release/loss |
| Startup time | Reasonable for a packaged desktop app |
| Idle CPU | Reduced when tracking is paused |

These are engineering targets, not hard claims for all hardware.

### 15.1 Optimization order

When performance is poor:

1. profile;
2. reduce preview refresh rate;
3. lower hand inference frequency;
4. lower camera resolution;
5. crop regions of interest when reliable;
6. avoid frame copies;
7. use MediaPipe asynchronous/live-stream mode appropriately;
8. consider ONNX Runtime or native optimization only for measured bottlenecks;
9. consider moving specific hot paths to Rust/C++ only as a final step.

---

## 16. Privacy and Security

Requirements:

- process video locally;
- do not save camera frames by default;
- do not transmit frames;
- no analytics or telemetry by default;
- make debug frame recording an explicit opt-in;
- display an obvious tracking-active indicator;
- release all synthetic key and mouse states on exit;
- arbitrary command execution is not part of the MVP;
- redact unnecessary personal paths from user-facing error messages.

Add a privacy page:

```text
All camera processing occurs locally on this device.
Meyes does not upload or store video unless diagnostic recording is explicitly enabled.
```

---

## 17. Accessibility and UX

The application itself must not depend only on eye control.

Requirements:

- fully usable through keyboard;
- visible focus indicators;
- scalable UI;
- clear pause control;
- global emergency shortcut;
- high-contrast status indicators;
- no color-only status meaning;
- tooltips for gesture thresholds;
- provide a setup wizard on first launch.

Default emergency shortcut:

```text
Ctrl + Alt + F12
```

Allow customization but always ensure at least one reliable pause mechanism exists.

Setup wizard:

1. choose camera;
2. position face;
3. verify eye detection;
4. verify left/right hand labels;
5. calibrate gaze;
6. test wink gestures without executing clicks;
7. test temple gestures without scrolling;
8. review default bindings;
9. enable live control.

---

## 18. Logging and Diagnostics

Use structured messages with categories:

```text
APP
CAMERA
FACE
HAND
GAZE
GESTURE
BINDING
INPUT
PERFORMANCE
CONFIG
```

Log:

- startup and shutdown;
- selected camera;
- camera reconnection;
- model initialization;
- configuration migration;
- gesture events;
- input errors;
- worker crashes;
- rolling performance metrics.

Do not log every frame.

Use rotating logs with conservative size limits.

Diagnostics panel must display recent semantic events, not raw personal imagery by default.

---

## 19. Suggested Project Structure

```text
meyes/
├── README.md
├── CODEX_SPEC.md
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── src/
│   └── meyes/
│       ├── __init__.py
│       ├── __main__.py
│       ├── application.py
│       ├── constants.py
│       ├── domain/
│       │   ├── actions.py
│       │   ├── events.py
│       │   ├── observations.py
│       │   └── state.py
│       ├── camera/
│       │   ├── interface.py
│       │   ├── opencv_camera.py
│       │   └── worker.py
│       ├── vision/
│       │   ├── face_landmarker.py
│       │   ├── hand_landmarker.py
│       │   ├── gaze_features.py
│       │   ├── gaze_mapper.py
│       │   ├── temple_geometry.py
│       │   └── worker.py
│       ├── gestures/
│       │   ├── engine.py
│       │   ├── wink_detector.py
│       │   ├── temple_detector.py
│       │   ├── state_machine.py
│       │   └── timing.py
│       ├── calibration/
│       │   ├── models.py
│       │   ├── collector.py
│       │   ├── mapper.py
│       │   └── repository.py
│       ├── bindings/
│       │   ├── models.py
│       │   ├── defaults.py
│       │   ├── manager.py
│       │   └── repository.py
│       ├── input/
│       │   ├── interface.py
│       │   ├── windows_send_input.py
│       │   ├── key_map.py
│       │   └── worker.py
│       ├── filters/
│       │   ├── one_euro.py
│       │   └── statistics.py
│       ├── config/
│       │   ├── models.py
│       │   ├── manager.py
│       │   └── migrations.py
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── tray.py
│       │   ├── setup_wizard.py
│       │   ├── dashboard_page.py
│       │   ├── calibration_page.py
│       │   ├── bindings_page.py
│       │   ├── sensitivity_page.py
│       │   ├── camera_page.py
│       │   ├── profiles_page.py
│       │   └── diagnostics_page.py
│       ├── services/
│       │   ├── tracking_controller.py
│       │   ├── action_dispatcher.py
│       │   └── health_monitor.py
│       └── util/
│           ├── logging.py
│           ├── paths.py
│           └── clocks.py
├── tests/
│   ├── unit/
│   │   ├── test_wink_detector.py
│   │   ├── test_temple_state_machine.py
│   │   ├── test_binding_manager.py
│   │   ├── test_config_migration.py
│   │   └── test_one_euro_filter.py
│   ├── integration/
│   │   ├── test_action_dispatch.py
│   │   └── test_config_roundtrip.py
│   └── fixtures/
│       └── observation_sequences/
├── resources/
│   ├── icons/
│   ├── models/
│   └── defaults/
├── scripts/
│   ├── run_dev.ps1
│   ├── test.ps1
│   └── build_windows.ps1
└── dist/
```

---

## 20. Domain Models

### 20.1 Gesture events

```python
from enum import StrEnum

class GestureEventType(StrEnum):
    LEFT_WINK = "LEFT_WINK"
    RIGHT_WINK = "RIGHT_WINK"
    LEFT_TEMPLE_TAP = "LEFT_TEMPLE_TAP"
    RIGHT_TEMPLE_TAP = "RIGHT_TEMPLE_TAP"
    LEFT_TEMPLE_HOLD_START = "LEFT_TEMPLE_HOLD_START"
    RIGHT_TEMPLE_HOLD_START = "RIGHT_TEMPLE_HOLD_START"
    LEFT_TEMPLE_HOLD_END = "LEFT_TEMPLE_HOLD_END"
    RIGHT_TEMPLE_HOLD_END = "RIGHT_TEMPLE_HOLD_END"
```

### 20.2 Action models

Use a discriminated union with Pydantic.

Conceptual example:

```python
class MouseClickAction(BaseModel):
    type: Literal["mouse_click"]
    button: Literal["left", "right", "middle"]

class MouseScrollAction(BaseModel):
    type: Literal["mouse_scroll"]
    amount: int

class ContinuousScrollAction(BaseModel):
    type: Literal["mouse_scroll_continuous"]
    amount: int
    interval_ms: int

class KeyboardShortcutAction(BaseModel):
    type: Literal["keyboard_shortcut"]
    keys: list[str]

class DisabledAction(BaseModel):
    type: Literal["disabled"]
```

### 20.3 Observation timestamps

Every observation must contain:

```text
capture_timestamp
processed_timestamp
confidence
```

Use these values to reject stale data and measure latency.

---

## 21. Testing Strategy

### 21.1 Unit tests

Required:

- both-eye blink does not emit left or right wink;
- left wink emits one event;
- sustained left wink does not repeat during cooldown;
- temple candidate rejected when stability duration is insufficient;
- temple tap emitted only after release;
- temple hold start emitted exactly once;
- hold end emitted after release;
- hold end emitted after observation timeout;
- left/right hand mirror conversion;
- binding validation;
- unsupported key rejection;
- config round-trip;
- corrupt config recovery;
- cursor filter behavior;
- all input states released after exception.

### 21.2 Recorded observation tests

Do not require a webcam for most gesture tests.

Store normalized observation sequences as JSON fixtures:

```json
[
  {
    "t_ms": 0,
    "left_eye_openness": 0.30,
    "right_eye_openness": 0.31
  },
  {
    "t_ms": 160,
    "left_eye_openness": 0.10,
    "right_eye_openness": 0.30
  }
]
```

Feed them into the gesture engine and assert emitted events.

### 21.3 Manual test matrix

Test:

- normal lighting;
- dim lighting;
- eyeglasses;
- partial face movement;
- hand briefly passing near face;
- wrong hand near wrong temple;
- both hands visible;
- hand exits camera while holding;
- webcam disconnect;
- app pause during scroll;
- app exit during key-down state;
- mirror on/off;
- multiple camera indices;
- 100%, 125%, and 150% Windows display scaling.

### 21.4 Input safety test mode

Provide a test mode in which gestures are detected and displayed but no OS input is injected.

This mode is required during setup and diagnostics.

---

## 22. MVP Implementation Phases

### Phase 0 — Repository bootstrap

Deliver:

- `pyproject.toml`;
- source layout;
- logging;
- config model;
- test setup;
- Ruff;
- type checker;
- PowerShell scripts;
- basic PySide6 window.

Acceptance:

- application launches;
- tests run;
- lint passes.

### Phase 1 — Camera and diagnostics preview

Deliver:

- camera enumeration;
- latest-frame capture;
- mirrored preview;
- measured FPS;
- camera error recovery;
- pause/resume.

Acceptance:

- UI remains responsive;
- camera can be changed;
- camera failure is shown clearly.

### Phase 2 — Face, eyes, and wink events

Deliver:

- Face Landmarker integration;
- eye openness values;
- independent wink detector;
- event diagnostics;
- no OS clicks yet.

Acceptance:

- natural both-eye blinks do not trigger wink events in ordinary testing;
- one sustained wink produces at most one event.

### Phase 3 — Hand and temple gestures

Deliver:

- Hand Landmarker integration;
- temple anchors;
- normalized distances;
- mirror correction;
- tap/hold state machine;
- timeout handling.

Acceptance:

- tap and hold are distinguishable;
- passing a hand near the face does not immediately trigger;
- continuous state ends after tracking loss.

### Phase 4 — Binding and Windows input

Deliver:

- binding models;
- default profile;
- Windows SendInput backend;
- click, scroll, shortcut, and pause actions;
- test mode.

Acceptance:

- defaults work;
- bindings persist;
- pause releases all active actions;
- user can disable any gesture.

### Phase 5 — Gaze cursor and calibration

Deliver:

- normalized gaze features;
- nine-point calibration;
- gaze mapper;
- smoothing;
- cursor movement;
- cursor freeze during temple gesture.

Acceptance:

- user can reach all broad screen regions after calibration;
- loss of face does not cause pointer jumps;
- recalibration can be performed from UI.

### Phase 6 — Complete UI and profiles

Deliver:

- dashboard;
- calibration;
- bindings;
- sensitivity;
- camera;
- profiles;
- diagnostics;
- tray controls;
- setup wizard.

Acceptance:

- all primary settings can be changed without editing JSON;
- profile import/export works;
- defaults can be restored.

### Phase 7 — Packaging and hardening

Deliver:

- packaged Windows build;
- application icon;
- startup error handling;
- configuration migration;
- rotating logs;
- README installation instructions;
- privacy notice;
- smoke-test checklist.

Acceptance:

- packaged app starts on a clean Windows machine with supported runtime dependencies bundled;
- app exits cleanly;
- no camera frames are stored by default.

---

## 23. MVP Acceptance Criteria

The MVP is complete only when all conditions below are met.

### Core interaction

- [ ] Webcam can be selected and previewed.
- [ ] Gaze can move the cursor after calibration.
- [ ] Left wink can trigger one left click.
- [ ] Right wink can trigger one right click.
- [ ] Normal both-eye blink does not trigger either click under ordinary conditions.
- [ ] Right-temple tap scrolls up by default.
- [ ] Left-temple tap scrolls down by default.
- [ ] Holding a temple starts continuous scroll.
- [ ] Releasing or losing tracking stops continuous scroll.
- [ ] Tracking can be paused with UI, tray, and emergency shortcut.

### Customization

- [ ] Every supported gesture can be disabled.
- [ ] Every supported gesture can be mapped to a supported mouse action.
- [ ] Every supported gesture can be mapped to a supported keyboard shortcut.
- [ ] Tap and hold actions are configured separately.
- [ ] Sensitivity and timing values are configurable.
- [ ] Configuration persists after restart.
- [ ] Default bindings can be restored.

### Reliability

- [ ] The UI does not freeze while tracking.
- [ ] A missing webcam does not crash the application.
- [ ] A disconnected webcam causes continuous actions to stop.
- [ ] Stale observations are ignored.
- [ ] All synthetic input states are released on pause and shutdown.
- [ ] Corrupt configuration is recovered safely.
- [ ] Logging is available for diagnosis.

### Privacy

- [ ] Frames remain local.
- [ ] Frames are not stored by default.
- [ ] No telemetry is sent.
- [ ] Diagnostic recording requires explicit opt-in.

---

## 24. Future Enhancements

Do not implement these before the MVP is stable:

- ONNX gaze-estimation model;
- personalized ML calibration;
- per-application profiles;
- automatic profile switching;
- drag-and-drop gesture;
- double-wink gesture;
- head-pose gestures;
- dwell click;
- edge scroll zones;
- virtual overlay buttons;
- multi-monitor calibration;
- accessibility onboarding presets;
- speech feedback;
- sound feedback;
- portable build;
- Linux backend;
- macOS backend;
- optional Rust extension for measured bottlenecks;
- dedicated Tobii or infrared eye-tracker integrations.

---

## 25. README Summary Copy

Use this initial copy in `README.md`:

```markdown
# Meyes

Meyes is a Windows desktop application that lets users control the mouse using eye gaze and configurable facial or hand gestures.

Default controls:

- gaze moves the pointer;
- left wink performs left click;
- right wink performs right click;
- right-temple gesture scrolls up;
- left-temple gesture scrolls down.

Every gesture can be rebound to supported mouse or keyboard actions. Camera processing runs locally on the device.

> Status: early development. Meyes is not a medical device and should not be relied upon for safety-critical operation.
```

---

## 26. First Codex Task

Start with **Phase 0 and Phase 1**.

Create a runnable repository that includes:

1. Python 3.11 project configuration.
2. PySide6 desktop window.
3. Camera selector.
4. OpenCV camera worker.
5. Latest-frame-only buffering.
6. Mirrored preview.
7. Start, pause, resume, and stop controls.
8. FPS and camera-health indicators.
9. Local JSON configuration with Pydantic validation.
10. Rotating logs.
11. Ruff, type checking, and pytest setup.
12. Unit tests for configuration and camera-state logic.
13. `README.md`, `CHANGELOG.md`, and Windows PowerShell development scripts.

Do not integrate MediaPipe until the camera pipeline and application lifecycle are stable.

After implementation, run all available checks and report:

- commands executed;
- test results;
- generated project tree;
- known limitations;
- exact next task for Phase 2.
