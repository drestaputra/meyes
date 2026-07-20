# 2026-07-20 - Safe profile lifecycle

## Summary

Completed the bounded Phase 4F profile lifecycle workflow without connecting operating-system
input. Users can rename, restore, and delete inactive user profiles through explicit controls,
while the built-in Default profile and active runtime profile remain protected.

## Added

- Repository operations for inactive profile rename, restore-from-Default, and recoverable
  deletion.
- A Profiles lifecycle panel with plain-language protection state, validated rename input,
  restore confirmation, and exact-name delete confirmation.
- Local deletion backups named with a UTC timestamp and excluded from the active JSON catalog.
- Controller-level protections that reject lifecycle changes for Default and the active profile,
  even if UI controls are bypassed.
- Automatic selection fallback to the active profile after the selected inactive profile is
  removed.
- Repository, controller, responsive UI, feedback-scroll, and MainWindow integration tests.

## Safety decisions

- Rename writes and fsyncs the complete renamed snapshot before retiring the original file. If
  the original cannot be retired, the new destination is removed and the original remains.
- Delete moves the JSON file to a same-directory `.deleted-<UTC timestamp>.bak` recovery copy
  instead of permanently unlinking it.
- Restore replaces all six bindings from the built-in Default snapshot but preserves the user
  profile name.
- Rename, delete, and restore are limited to inactive user profiles. They do not pause, activate,
  dispatch, persist an active-profile preference, or mutate the fake runtime snapshot.
- Delete requires an exact case-sensitive copy of the selected profile name. Restore requires a
  separate acknowledgement checkbox.
- Profile feedback uses a page-owned timer, so pending scroll work is cancelled safely when the
  Qt page is destroyed. The same ownership fix was applied to the Bindings feedback timer.
- No Windows input backend or operating-system dispatch path was introduced.

## Verification

Focused Phase 4F gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check src\meyes\bindings\repository.py src\meyes\ui\profile_controller.py src\meyes\ui\profiles_page.py src\meyes\ui\bindings_page.py src\meyes\ui\theme.py tests\unit\test_binding_repository.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py tests\unit\test_bindings_page.py tests\unit\test_main_window.py
.\.venv\Scripts\python.exe -m ruff check src\meyes\bindings\repository.py src\meyes\ui\profile_controller.py src\meyes\ui\profiles_page.py src\meyes\ui\bindings_page.py src\meyes\ui\theme.py tests\unit\test_binding_repository.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py tests\unit\test_bindings_page.py tests\unit\test_main_window.py
.\.venv\Scripts\python.exe -m mypy src\meyes\bindings\repository.py src\meyes\ui\profile_controller.py src\meyes\ui\profiles_page.py src\meyes\ui\bindings_page.py src\meyes\ui\theme.py tests\unit\test_binding_repository.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py tests\unit\test_bindings_page.py tests\unit\test_main_window.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_binding_repository.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py tests\unit\test_bindings_page.py tests\unit\test_main_window.py
```

- Ruff format: 10 focused files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 10 focused source files.
- Pytest: 86 passed in 6.47 seconds.

Full repository gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -q
```

- Ruff format: 93 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 93 source files.
- Pytest: 443 passed in 12.79 seconds.
- `git diff --check`: passed.
- Source/dependency audit found no Windows input backend or `SendInput`, `ctypes`, `pyautogui`,
  or `pynput` execution path.

Native Windows QA covered the Profiles workflow at `900 x 640` and `1400 x 900` with an
80-character profile name, rename, restore/delete confirmations, feedback scrolling, and active
runtime/config invariants. Both sizes retained a zero horizontal scroll range; compact layouts
use deliberate vertical scrolling.

## Known limitations

- Recovery backups are retained locally but do not yet have an in-app restore workflow.
- Rename intentionally treats case-only changes as the same case-insensitive Windows name.
- Import/export remains out of scope for this iteration.
- The global emergency shortcut, gaze calibration, Windows input backend, packaging, and native
  held-input verification remain pending.

## Next task

Build Phase 4G as a bounded, schema-validated profile import/export workflow with explicit
collision handling, inactive-only import, sanitized errors, and no runtime activation.
