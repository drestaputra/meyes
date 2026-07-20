# 2026-07-19 — Qt fake-only action simulation

## Summary

Composed the Phase 4 dispatcher into the runnable PySide6 event path without adding an
operating-system input backend. Live semantic gesture events now exercise the loaded binding
profile through `FakeInputExecutor`, while Diagnostics makes the simulation state, active
holds, result, fault, and bounded primitive trace visible.

## Added

- `ActionSimulationController`, owned by the Qt main thread, as the only runtime bridge into
  `ActionDispatcher`.
- A single-shot Qt timer derived from the dispatcher's next monotonic deadline for continuous
  actions, with delayed first ticks and no busy loop or catch-up burst.
- Strict executor construction that accepts only `FakeInputExecutor`, preserving the Safe Mode
  boundary at runtime.
- Bounded fake primitive records, drained independently from held-input state and exposed by
  typed Qt signals.
- Diagnostics fields for simulation state, profile, active holds, last dispatch result, and
  sanitized fault identity, plus a 50-row fake primitive trace.
- A responsive Diagnostics grid that keeps three equal columns when wide, moves the action
  panel below the observations when narrow, and provides vertical scrolling without hidden
  horizontal overflow. Long valid profile names are bounded visually with a full tooltip.
- Active-profile loading during application composition, including fail-closed all-disabled
  recovery for a missing or invalid user profile.
- Qt integration tests for signal delivery, duplicate suppression, continuous polling,
  malformed payload containment, bounded records, contained executor faults, reentrant close,
  terminal shutdown, and release ordering.

## Safety decisions

- The runtime adapter rejects every executor that is not a `FakeInputExecutor` instance or
  subclass. No `SendInput`, `ctypes`, automation package, or OS input path was introduced.
- Camera/tracking pause requests use queued Qt connections so lifecycle callbacks cannot cause
  a nested dispatcher call.
- Pause and close stop the timer first, gate dispatch, and release simulated held state before
  vision or camera shutdown continues.
- Clock exceptions, non-numeric values, booleans, negative values, and non-finite values pause
  the simulation fail-safe.
- The UI calls the records a simulation and states that OS input is disconnected; it does not
  present fake clicks, keys, or scrolling as operating-system effects.

## Verification

Focused Phase 4C gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check src\meyes\application.py src\meyes\input\fake.py src\meyes\services\action_dispatcher.py src\meyes\ui\action_simulation.py src\meyes\ui\camera_dashboard.py src\meyes\ui\diagnostics_page.py src\meyes\ui\main_window.py src\meyes\ui\theme.py tests\unit\test_action_simulation.py tests\unit\test_diagnostics_page.py tests\unit\test_input_interface.py tests\unit\test_main_window.py
.\.venv\Scripts\python.exe -m ruff check src\meyes\application.py src\meyes\input\fake.py src\meyes\services\action_dispatcher.py src\meyes\ui\action_simulation.py src\meyes\ui\camera_dashboard.py src\meyes\ui\diagnostics_page.py src\meyes\ui\main_window.py src\meyes\ui\theme.py tests\unit\test_action_simulation.py tests\unit\test_diagnostics_page.py tests\unit\test_input_interface.py tests\unit\test_main_window.py
.\.venv\Scripts\python.exe -m mypy src\meyes\application.py src\meyes\input\fake.py src\meyes\services\action_dispatcher.py src\meyes\ui\action_simulation.py src\meyes\ui\camera_dashboard.py src\meyes\ui\diagnostics_page.py src\meyes\ui\main_window.py src\meyes\ui\theme.py tests\unit\test_action_simulation.py tests\unit\test_diagnostics_page.py tests\unit\test_input_interface.py tests\unit\test_main_window.py
.\.venv\Scripts\python.exe -m pytest tests\unit\test_action_simulation.py tests\unit\test_diagnostics_page.py tests\unit\test_main_window.py tests\unit\test_input_interface.py -q
```

- Ruff format: 12 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 12 source files.
- Pytest: 24 passed in 1.81 seconds.

Full repository gate, using the virtual-environment executables equivalent to
`scripts/check.ps1` because the current shell's global Python shim has no `uv` module:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -q
```

- Ruff format: 81 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 81 source files.
- Pytest: 334 passed in 8.01 seconds.
- `git diff --check`: passed.
- Source/dependency audit: no `SendInput`, `ctypes`, `pyautogui`, or `pynput` path found.

Native Windows visual QA rendered the populated Diagnostics view at `1400 x 900` and the
application minimum `900 x 640`. The wide view retained three equal cards. The minimum-width
view reflowed to two observation cards with the full-width action card below, kept horizontal
scroll range at zero, and exposed the additional height through vertical scrolling.

## Known limitations

- Fake simulation is intentionally the only runtime binding execution. Mouse and keyboard
  output remain disconnected.
- Binding profiles are loaded from configuration but are not yet selectable or editable in
  the UI.
- The emergency pause shortcut, gaze calibration, OS input backend, packaging, and native
  held-input verification remain pending.

## Next task

Add the user-visible profile and binding management workflow while retaining fake-only
execution, then validate import/export, restore-default, and active-profile transitions before
considering any Windows input backend.
