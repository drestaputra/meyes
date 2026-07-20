# 2026-07-20 - Windows live safety foundation

## Summary

Added the dormant Windows safety layer required before the native executor may be wired into the
application. The service can register a system-wide emergency shortcut, route its native Windows
message through Qt, and detect physically held buttons/modifiers before an arm attempt. It remains
unwired, so the runnable application still registers no global shortcut and sends no OS input.

## Added

- A narrow injectable boundary for `RegisterHotKey`, `UnregisterHotKey`, `GetAsyncKeyState`, and
  Windows `MSG` parsing.
- A Qt native event filter for both `windows_generic_MSG` and `windows_dispatcher_MSG` events.
- The emergency combination `Ctrl+Alt+Shift+F11` with `MOD_NOREPEAT`.
- Stable physical-input preflight reporting for left/right/middle mouse buttons, Shift, Ctrl, Alt,
  and both Windows keys.
- Idempotent registration/cleanup and retryable state if native unregistration fails.
- Fake-boundary unit tests plus a no-registration native User32/message-layout smoke check.

## Safety decisions

- F12 is not used because Microsoft documents it as reserved for the debugger at all times.
- Registration failure leaves the service unregistered and removes the Qt event filter.
- Unregistration failure keeps the event filter and registered state alive so emergency handling
  is not silently lost and cleanup can be retried.
- The service is not constructed by `MainWindow`; this iteration never called `RegisterHotKey`,
  `UnregisterHotKey`, or `GetAsyncKeyState` through the real adapter.
- Physical preflight uses only the documented high-order down-state bit and ignores the unreliable
  recent-press bit.

## Official API references

- [Microsoft RegisterHotKey function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey)
- [Microsoft UnregisterHotKey function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-unregisterhotkey)
- [Microsoft GetAsyncKeyState function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getasynckeystate)
- [Microsoft WM_HOTKEY message](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-hotkey)
- [Qt native event filter](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractNativeEventFilter.html)

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check src\meyes\input\windows_safety.py tests\unit\test_windows_safety.py
.\.venv\Scripts\python.exe -m ruff check src\meyes\input\windows_safety.py tests\unit\test_windows_safety.py
.\.venv\Scripts\python.exe -m mypy src\meyes\input\windows_safety.py tests\unit\test_windows_safety.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_windows_safety.py
```

- Ruff format: 2 focused files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 2 source files.
- Pytest: 11 passed in 0.13 seconds.

Full repository gate:

- Ruff format: 97 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 97 source files.
- Pytest: 477 passed in 14.18 seconds.
- `git diff --check`: passed.

## Known limitations

- `MainWindow` does not construct or register this service yet.
- The emergency signal is not yet connected to tracking pause and native release.
- Physical state checks can return zero when desktop access/UIPI prevents the query; the live arm
  workflow must combine preflight with release-first initialization and visible fail-closed state.
- A hotkey conflict can prevent registration and must block live arming.

## Next task

Integrate the emergency service with a per-session live runtime controller. Require explicit typed
consent, successful hotkey registration, clear physical preflight, and release-first initialization
before swapping from fake-only simulation to the native dispatcher. Emergency trigger, disarm,
fault, and shutdown must all pause tracking and release owned input.
