# 2026-07-19 — Safe profile management

## Summary

Added the bounded Phase 4D Profiles workflow without weakening MEYES Safe Mode. Users can
inspect the durable local catalog, create a complete all-disabled profile, activate a selected
profile through an explicit paused transition, and preview the active profile's six simulated
gesture bindings.

## Added

- A responsive Profiles page with catalog refresh, canonical active markers, inline operation
  feedback, accessible controls, and a read-only two-column binding preview.
- Collision-safe creation for validated user profiles. New profiles always contain all six
  bindable gestures and start disabled; creation never changes the active profile.
- Human-readable labels for every supported gesture and action without implying that simulated
  actions reached Windows.
- Controller and UI regression tests for validation, duplicate names, catalog warnings,
  activation, persistence and secondary rollback failure, startup recovery truthfulness,
  complete action labels, maximum-length names, accessibility, and narrow layouts.

## Changed

- Application composition now shares one profile repository between startup loading and the
  Profiles workflow.
- Profile activation stops polling, releases simulated held state, pauses tracking, loads the
  selected snapshot, and remains paused until the user explicitly resumes.
- The active-profile preference is persisted only after runtime activation succeeds. A save
  failure restores the previous runtime snapshot and leaves tracking paused. If that secondary
  rollback also fails, the visible profile is reconciled to the simulator-owned snapshot and
  the fault remains explicit.
- The top bar, profile catalog, and binding preview update from the same canonical active
  profile signal; maximum-length names are pixel-elided in the constrained top bar with the
  full value retained in its tooltip.
- Catalog reads disclose a sanitized warning when invalid or ambiguous files are ignored, and
  a missing or quarantined startup snapshot is not presented as a durable local profile.
- New profile files use an exclusive destination write so a late same-name collision cannot
  overwrite an existing profile.

## Verification

Focused Phase 4D gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check src\meyes\bindings\repository.py src\meyes\bindings\presentation.py src\meyes\ui\action_simulation.py src\meyes\ui\profile_controller.py src\meyes\ui\profiles_page.py src\meyes\application.py src\meyes\ui\main_window.py src\meyes\ui\theme.py tests\unit\test_binding_repository.py tests\unit\test_binding_presentation.py tests\unit\test_action_simulation.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py tests\unit\test_main_window.py
.\.venv\Scripts\python.exe -m ruff check src\meyes\bindings\repository.py src\meyes\bindings\presentation.py src\meyes\ui\action_simulation.py src\meyes\ui\profile_controller.py src\meyes\ui\profiles_page.py src\meyes\application.py src\meyes\ui\main_window.py src\meyes\ui\theme.py tests\unit\test_binding_repository.py tests\unit\test_binding_presentation.py tests\unit\test_action_simulation.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py tests\unit\test_main_window.py
.\.venv\Scripts\python.exe -m mypy src\meyes\bindings\repository.py src\meyes\bindings\presentation.py src\meyes\ui\action_simulation.py src\meyes\ui\profile_controller.py src\meyes\ui\profiles_page.py src\meyes\application.py src\meyes\ui\main_window.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_binding_repository.py tests\unit\test_binding_presentation.py tests\unit\test_action_simulation.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py tests\unit\test_main_window.py
```

- Ruff format and lint: passed for all 14 focused files.
- Mypy strict: no issues in the seven focused source files.
- Pytest: 74 passed in 3.90 seconds.

Full repository gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -q
```

- Ruff format: 87 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 87 source files.
- Pytest: 376 passed in 11.76 seconds.
- `git diff --check`: passed.
- Source/dependency audit found no Windows input backend or `SendInput`, `ctypes`, `pyautogui`,
  or `pynput` execution path.
- A final read-only adversarial re-audit confirmed rollback reconciliation, recovery-snapshot
  disclosure, maximum-length responsive behavior, and exclusive late-collision rejection.

Native Windows visual QA covered the populated Profiles page at `700 x 640` and `1100 x 900`.
Both sizes kept the horizontal scroll range at zero; the compact view exposed the lower binding
preview through deliberate vertical scrolling. A full `900 x 640` shell render with an active
80-character profile also retained zero horizontal overflow, a bounded top-bar label, and the
full name in tooltips.

## Known limitations

- The binding preview is read-only. Binding creation or editing is not part of this iteration.
- Profile rename, deletion, import/export, and restore-default workflows remain pending.
- The global emergency shortcut, gaze calibration, Windows input backend, packaging, and native
  held-input verification remain pending.
- Fake simulation remains the only runtime action path; mouse and keyboard output stay
  disconnected.

## Next task

Build Phase 4E as a safe draft-based binding editor with save-as-copy behavior and isolated
preview, while retaining fake-only execution and the explicit arm/pause boundary.
