# 2026-07-20 - Windows Live Input integration

## Summary

Connected the tested Windows `SendInput` executor and emergency safety boundary to the runnable
application. MEYES still opens in Safe Mode, but a Windows user can now deliberately arm real click,
scroll, key, and shortcut actions for the current session from the new Live Input view.

## Added

- A persistent **Live Input** navigation view with non-color Safe/Live/Fault status.
- Exact `ENABLE LIVE INPUT` consent that is cleared after each attempt and never persisted.
- Camera-running UI gate, hotkey-first registration, physical-input preflight, and release-first
  executor initialization.
- Parallel event routing: Diagnostics keeps its fake trace while the native dispatcher receives
  the same semantic event only when explicitly armed.
- Persistent bottom-bar emergency chord and truthful dashboard input-mode status.
- Automatic live disarm on emergency, user request, camera pause/stop/fault, profile transition,
  executor fault, page close, and application close.
- Pending-profile recovery that prevents a release fault from returning to Safe Mode with a stale
  live binding snapshot.
- Backward-compatible migration from the formerly planned `Ctrl+Alt+F12` value to
  `Ctrl+Alt+Shift+F11`; other shortcut configuration values are rejected.

## Safety decisions

- Safe Mode is the only startup state. Consent and armed state are not saved.
- The global emergency chord must register successfully before the native executor is constructed.
- Physical mouse buttons and Ctrl/Alt/Shift/Windows keys must be released before arming.
- MEYES releases its owned synthetic state before each arm and before every transition back to
  Safe Mode.
- A release or profile synchronization failure remains visibly faulted and retains the emergency
  registration for recovery; it cannot silently re-arm.
- Pointer movement remains unavailable until gaze calibration and screen mapping are implemented.
- Automated UI and lifecycle tests inject fake Windows APIs and a fake executor; they send no real
  mouse or keyboard input.

## Native QA

- Native Windows render: passed at 1200 × 760 with the complete Live Input consent workflow and
  persistent Safe Mode bar visible without clipping.
- Composition smoke: `MainWindow` remained Safe, constructed no native service, registered no
  hotkey, and closed cleanly.
- Win32 emergency smoke: the real `Ctrl+Alt+Shift+F11` chord registered successfully, physical
  preflight reported clear, and unregistration returned the service to `registered=False`.
- No QA command invoked real `SendInput`; actual OS output remains a deliberate user-controlled
  application action.

## Verification

Focused integration gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes\ui\live_input.py src\meyes\ui\live_input_page.py src\meyes\ui\main_window.py
.\.venv\Scripts\python.exe -m mypy src\meyes\ui\live_input.py src\meyes\ui\live_input_page.py src\meyes\ui\main_window.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_live_input.py tests\unit\test_live_input_page.py tests\unit\test_main_window.py tests\unit\test_config_manager.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 34 passed in 3.83 seconds.

Full repository gate:

- Ruff format: 101 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 101 source files.
- Pytest: 495 passed in 15.50 seconds.
- `git diff --check`: passed.

## Known limitations

- Gaze-calibrated pointer movement is not implemented; `move_pointer` remains deliberately gated.
- Windows UIPI can block input into a higher-integrity target without a specific error.
- Gesture accuracy depends on camera placement, lighting, occlusion, and user-specific tuning.
- Profile import/export, tray controls, packaging, and a clean-machine judge smoke remain pending.

## Next task

Run the complete verification gate and native UI audit, then continue with profile import/export or
the gaze calibration foundation without weakening the Live Input safety boundary.
