# 2026-07-19 — Fake-only action dispatcher

## Summary

Completed the next Phase 4 safety gate with a synchronous, framework-neutral action
dispatcher exercised only through `FakeInputExecutor`. It converts validated semantic events
and binding snapshots into deterministic primitive calls while containing failures and
remaining disconnected from the Qt runtime and operating-system input.

## Added

- A dispatcher state gate with `PAUSED`, `ACTIVE`, `FAULTED`, and terminal `CLOSED` states.
- Safe Mode startup that requires an explicit release-all preflight before arming.
- Per-producer ordering channels for left/right winks and left/right temple streams, including
  at-most-once attempts, duplicate/stale suppression, and same-sequence hold start-to-end
  support for timeout/coarse-clock paths.
- Dispatcher-owned profile snapshots so external profile mutation cannot change an active
  hold action.
- Logical hold sessions for every hold binding and reference-counted ownership when two holds
  share one physical mouse button.
- Poll-driven continuous scroll with delayed first tick, deterministic left-to-right ordering,
  at most one tick per side per poll, no catch-up bursts, and finite strictly advancing
  deadlines.
- Mouse click, double-click, down/up, finite/continuous scroll, keyboard key/shortcut, disabled,
  and tracking lifecycle action semantics through the fake executor.
- Lifecycle cleanup for pause, explicit release, profile activation, producer epoch reset,
  recovery, and close.
- Best-effort tracking pause on contained faults, retryable global input release, and explicit
  recovery that always lands paused rather than resuming automatically.
- Reentrancy guards that reject nested dispatch/poll calls, defer safety pause/release requests,
  and prevent recursive cleanup or queued action replay.
- Immutable reports and snapshots for future runtime diagnostics without Qt dependencies.

## Safety decisions

- Continuous scroll does not fire on hold start. The first step is due only after the validated
  interval, so an immediate start/end pair produces no scroll.
- Gesture capture timestamps never drive scheduling; callers provide a validated monotonic
  dispatcher timestamp.
- Temple tap and hold events on the same anatomical side share one ordering cursor because
  they come from the same producer stream.
- A same-side tap received while a hold session is active is treated as a producer contract
  fault and releases all input before the tap action can run.
- Event identity is consumed before any executor call. A partially successful or failed action
  is never retried by replaying the same event.
- Click and double-click actions are suppressed while another hold owns the same physical
  button, avoiding an implicit mouse-up that could break the hold.
- Any executor, lifecycle callback, scheduling, ownership, or reentrancy fault gates the
  dispatcher before cleanup. Cleanup failure remains faulted and can be retried explicitly.
- Profile changes release all old ownership and leave the dispatcher paused; they never resume
  execution implicitly.

## Verification

Focused dispatcher gate:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check src\meyes\services tests\unit\test_action_dispatcher.py
.\.venv\Scripts\python.exe -m ruff check src\meyes\services tests\unit\test_action_dispatcher.py
.\.venv\Scripts\python.exe -m mypy src\meyes\services tests\unit\test_action_dispatcher.py
.\.venv\Scripts\python.exe -m pytest tests\unit\test_action_dispatcher.py -q
```

- Ruff format: 3 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 3 source files.
- Pytest: 53 passed in 0.67 seconds.

Full repository gate, using the virtual-environment executables equivalent to
`scripts/check.ps1` because the current shell's global Python shim has no `uv` module:

```powershell
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest
```

- Ruff format: 79 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 79 source files.
- Pytest: 321 passed in 7.90 seconds.

## Known limitations

- The dispatcher is not composed into `VisionController`, `MainWindow`, or another runtime
  adapter. Live gesture events still only appear in Safe Mode diagnostics.
- `FakeInputExecutor` is the only implementation used. No Windows `SendInput`, `ctypes`,
  automation library, global shortcut, Qt timer, worker thread, or sleep loop was added.
- Binding profiles are not yet selectable or editable in the UI.
- The emergency pause shortcut and native held-key/mouse release verification remain pending.

## Next task

Build the next Phase 4 runtime boundary in no-input mode: a Qt-owned adapter that feeds semantic
events into the dispatcher with `FakeInputExecutor`, polls deadlines on the main thread, exposes
state/fault diagnostics, and proves camera/tracking pause and shutdown release ordering before
any Windows backend is introduced.
