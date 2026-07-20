# 2026-07-20 - Dormant Windows SendInput executor

## Summary

Completed the first bounded native-input iteration by implementing a Windows `SendInput`
executor behind an unwired platform boundary. The runnable MEYES application remains fake-only:
it does not construct this executor, expose a live-mode control, or send operating-system input.

## Added

- ABI-aligned ctypes definitions for Win32 `INPUT`, `MOUSEINPUT`, `KEYBDINPUT`, and their union.
- A narrow injectable `SendInputApi` protocol and immutable packet descriptions so automated
  tests never call the real API.
- Native mappings for left/right/middle button down/up/click, bounded vertical wheel steps, the
  complete closed MEYES virtual-key vocabulary, and modifier shortcuts.
- Thread-safe tracking of only the keys and mouse buttons acquired by MEYES.
- Partial-send detection using the returned inserted-event count and bounded Windows error data.
- Reverse-acquisition release, retryable failed releases, and distinct aggregate reporting when
  both a transient input operation and its fail-safe cleanup fail.
- A native smoke check that loads `User32` and verifies the runtime `INPUT` structure size without
  sending any input event.

## Safety decisions

- Construction is opt-in and platform-specific. `ActionSimulationController` still accepts only
  `FakeInputExecutor`, and `MainWindow` has no path that constructs `WindowsSendInputExecutor`.
- Click and shortcut sequences are sent as ordered arrays. If Windows reports a prefix-only send,
  the executor applies ownership transitions only for that prefix, attempts cleanup, and reports
  the original failure.
- If the native boundary raises before returning an inserted count, press events are treated as
  possibly held and retained for cleanup rather than assumed absent.
- Release attempts continue after individual failures and leave failed owned states available for
  a later retry.
- Mouse wheel values use the documented `WHEEL_DELTA` of 120 per logical step.
- Calibrated pointer movement is deliberately not implemented in this backend iteration.
- No automated or manual QA step injected a real mouse or keyboard event.

## Official API references

- [Microsoft SendInput function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
- [Microsoft INPUT structure](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-input)
- [Microsoft KEYBDINPUT structure](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-keybdinput)
- [Microsoft MOUSEINPUT structure](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput)
- [Microsoft virtual-key codes](https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes)
- [Python ctypes documentation](https://docs.python.org/3/library/ctypes.html)

## Verification

Focused native-executor gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check src\meyes\input\interface.py src\meyes\input\fake.py src\meyes\input\windows_sendinput.py tests\unit\test_input_interface.py tests\unit\test_windows_sendinput.py
.\.venv\Scripts\python.exe -m ruff check src\meyes\input\interface.py src\meyes\input\fake.py src\meyes\input\windows_sendinput.py tests\unit\test_input_interface.py tests\unit\test_windows_sendinput.py
.\.venv\Scripts\python.exe -m mypy src\meyes\input\interface.py src\meyes\input\fake.py src\meyes\input\windows_sendinput.py tests\unit\test_input_interface.py tests\unit\test_windows_sendinput.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_input_interface.py tests\unit\test_windows_sendinput.py
```

- Ruff format: 5 focused files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 5 source files.
- Pytest: 31 passed in 0.53 seconds.

Full repository gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -q
```

- Ruff format: 95 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 95 source files.
- Pytest: 466 passed in 15.69 seconds.
- `git diff --check`: passed.

## Known limitations

- The runnable application remains Safe Mode/fake-only; no live executor is constructed or armed.
- Microsoft documents that UIPI can block `SendInput` without identifying UIPI as the cause.
- Physical keyboard state can interfere with injected keys; live arming therefore still requires
  a physical-key preflight.
- A global emergency pause shortcut is not yet implemented.
- Absolute pointer movement remains deferred until calibrated screen mapping exists.
- Native held-input recovery has not been manually exercised because this iteration intentionally
  sent no real input.

## Next task

Build the safety layer required before any live wiring: a global emergency pause shortcut,
physical modifier-key preflight, explicit user consent, release-first arm/disarm transitions, and
visible live-mode status. Keep Safe Mode as the default and fail closed on every initialization or
release error.
