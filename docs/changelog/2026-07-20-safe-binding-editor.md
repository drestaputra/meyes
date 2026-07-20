# 2026-07-20 — Safe binding editor

## Summary

Completed the bounded Phase 4E Bindings workflow without connecting operating-system input.
Users can edit all six semantic gesture bindings through validated controls, inspect the last
valid draft snapshot, and save it as a new inactive profile without editing JSON.

## Added

- A typed editor codec covering every supported MVP action: disabled, mouse click/double-click,
  mouse down/up, finite and continuous scroll, keyboard key/shortcut, and tracking lifecycle
  actions.
- Plain-language parameter grammars and corrective messages for mouse buttons, bounded scroll,
  continuous cadence, the closed key vocabulary, and modifier shortcuts.
- An isolated `BindingEditorController` with row edit/reset, reset-all, explicit active-snapshot
  reload, dirty tracking, stale-source disclosure, and exclusive save-as-copy.
- A responsive Bindings page with six accessible editor rows, per-row inline errors, an
  isolated last-valid preview, source/runtime status, and local save feedback.
- Automatic catalog synchronization after a copy is saved, without changing the active profile,
  application preference, dispatcher snapshot, or tracking state.
- Codec, controller, Qt UI, responsive-layout, persistence, and MainWindow integration tests.

## Safety decisions

- The editor controller has no dispatcher or input-executor dependency. Editing and previewing
  cannot dispatch even fake actions.
- Mouse-down and continuous-scroll choices appear only for temple hold gestures, matching the
  binding model's lifecycle constraints.
- Invalid row text remains visible with an inline correction but never replaces the last valid
  draft action or enables saving.
- A dirty or invalid draft survives an external active-profile change. Discarding it requires
  the explicitly worded “Discard draft and load active snapshot” action.
- Saving always uses the repository's exclusive create path and produces a new inactive profile.
  Activation remains a separate Profiles workflow that pauses and releases first.
- The UI explicitly says that preview does not dispatch, simulate, activate, or test actions;
  no Windows input backend was introduced.

## Verification

Focused Phase 4E gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check src\meyes\bindings\editor.py src\meyes\bindings\repository.py src\meyes\ui\binding_editor_controller.py src\meyes\ui\bindings_page.py src\meyes\ui\main_window.py src\meyes\ui\profile_controller.py src\meyes\ui\theme.py tests\unit\test_binding_editor_codec.py tests\unit\test_binding_editor_controller.py tests\unit\test_bindings_page.py tests\unit\test_main_window.py tests\unit\test_binding_repository.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py
.\.venv\Scripts\python.exe -m ruff check src\meyes\bindings\editor.py src\meyes\bindings\repository.py src\meyes\ui\binding_editor_controller.py src\meyes\ui\bindings_page.py src\meyes\ui\main_window.py src\meyes\ui\profile_controller.py src\meyes\ui\theme.py tests\unit\test_binding_editor_codec.py tests\unit\test_binding_editor_controller.py tests\unit\test_bindings_page.py tests\unit\test_main_window.py tests\unit\test_binding_repository.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py
.\.venv\Scripts\python.exe -m mypy src\meyes\bindings\editor.py src\meyes\bindings\repository.py src\meyes\ui\binding_editor_controller.py src\meyes\ui\bindings_page.py src\meyes\ui\main_window.py src\meyes\ui\profile_controller.py src\meyes\ui\theme.py tests\unit\test_binding_editor_codec.py tests\unit\test_binding_editor_controller.py tests\unit\test_bindings_page.py tests\unit\test_main_window.py tests\unit\test_binding_repository.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_binding_editor_codec.py tests\unit\test_binding_editor_controller.py tests\unit\test_bindings_page.py tests\unit\test_main_window.py tests\unit\test_binding_repository.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py
```

- Ruff format: 14 focused files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 14 focused source files.
- Pytest: 94 passed in 4.90 seconds.

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
- Pytest: 418 passed in 10.85 seconds.
- `git diff --check`: passed.
- Source/dependency audit found no Windows input backend or `SendInput`, `ctypes`, `pyautogui`,
  or `pynput` execution path.

Native Windows QA covered a full Bindings shell at `900 x 640` and `1400 x 900`, including an
80-character active profile, invalid inline input, a valid keyboard edit, and save-as-copy.
Both sizes retained a zero horizontal scroll range; compact layouts use deliberate vertical
scrolling for the six complete editor rows and isolated preview.

## Known limitations

- Drafts are intentionally in-memory and are not restored after an application restart.
- The editor does not execute or test actions; preview shows only the last valid draft snapshot.
- Keyboard shortcuts currently use validated text rather than a temporary capture control.
- Saving creates a new inactive profile. Activating it remains an explicit Profiles operation.
- Profile rename, deletion, import/export, and restore-default workflows remain pending.
- The global emergency shortcut, gaze calibration, Windows input backend, packaging, and native
  held-input verification remain pending.

## Next task

Build Phase 4F as a fail-safe profile lifecycle workflow: rename, explicit-confirmation delete,
and restore-default behavior with active-profile protections. Keep import/export as a separate
bounded iteration.
