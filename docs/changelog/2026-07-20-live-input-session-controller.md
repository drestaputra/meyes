# 2026-07-20 - Live Input session controller

## Summary

Added the fail-closed Qt controller that will own real Windows input sessions. It remains outside
`MainWindow`, so this iteration cannot be activated from the runnable application and sent no real
mouse or keyboard input.

## Added

- Exact, case-sensitive per-session consent using `ENABLE LIVE INPUT`; consent is never persisted.
- Hotkey-first startup: `Ctrl+Alt+Shift+F11` must register before executor construction.
- Physical mouse/modifier preflight before the native executor is lazily constructed.
- Release-first event-epoch reset and dispatcher arm before the state becomes visibly armed.
- A second dispatcher that reuses the validated binding, hold-ownership, continuous-action, and
  fault-containment rules without weakening the existing fake Diagnostics path.
- Emergency, ordinary disarm, profile transition, executor fault, and terminal close paths.
- Immutable live status snapshots and Qt signals for later persistent UI integration.

## Safety decisions

- Safe Mode remains the default and the controller constructs neither Win32 service until arm is
  explicitly requested.
- Registration or physical-preflight failure blocks native executor construction.
- A release failure leaves the controller faulted and retains the emergency shortcut so cleanup
  can be retried instead of falsely reporting Safe Mode.
- Emergency activation gates/releases the live dispatcher before requesting camera pause.
- Profile changes disarm live execution and require the consent phrase again.
- Shutdown enters a terminal state and attempts input release before hotkey cleanup.
- Automated verification injects `FakeInputExecutor` and a fake Windows safety API. No test invokes
  the real `SendInput`, `RegisterHotKey`, `UnregisterHotKey`, or `GetAsyncKeyState` functions.

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check src\meyes\ui\live_input.py tests\unit\test_live_input.py
.\.venv\Scripts\python.exe -m ruff check src\meyes\ui\live_input.py tests\unit\test_live_input.py
.\.venv\Scripts\python.exe -m mypy src\meyes\ui\live_input.py tests\unit\test_live_input.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_live_input.py
```

- Ruff format: 2 focused files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 2 source files.
- Pytest: 11 passed in 0.50 seconds.

Full repository gate:

- Ruff format: 99 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 99 source files.
- Pytest: 488 passed in 13.89 seconds.
- `git diff --check`: passed.

## Known limitations

- `MainWindow` does not construct the controller, route semantic events into it, expose the consent
  workflow, or register the emergency shortcut yet.
- Pointer movement remains disabled pending calibrated screen mapping.
- Windows UIPI can block `SendInput` without a specific error and cannot be bypassed by the app.
- The default binding profile is suitable for real click/scroll evaluation, but live use still
  depends on camera/gesture quality and must always retain visible Safe/Live status.

## Next task

Wire this controller into `MainWindow` through a persistent Live Input panel. Keep the fake trace
active for diagnostics, route semantic events to live execution only while armed, synchronize
profile changes, disarm on camera pause/stop/fault and window close, and show the emergency chord
whenever live execution is available.
