# 2026-07-19 — Binding and action foundation

## Summary

Started Phase 4 with a pure, platform-neutral safety foundation: a closed action vocabulary,
complete logical gesture profiles, exact built-in defaults, fail-closed user-profile
persistence, and an input protocol exercised only by an in-memory fake. No gesture event,
Qt controller, Windows API, mouse, keyboard, or scroll output is connected to these models.

## Added

- Frozen Pydantic action variants for disabled, mouse click/double-click/down/up, finite and
  continuous scroll, keyboard key/shortcut, and tracking lifecycle requests.
- A closed mouse-button and keyboard-key vocabulary with normalized key names.
- Nonzero scroll bounds of `-20..20` and continuous intervals of `25..5000 ms`.
- Shortcut validation for one to five unique keys with exactly one non-modifier key.
- Six user-facing logical gestures. Temple hold start and end map to one logical hold, so end
  is a lifecycle stop signal rather than a separately configurable action.
- A complete profile invariant: every gesture must be explicit, including disabled gestures.
- Read-only binding mappings plus serialized revalidation of preconstructed Pydantic action
  instances, including instances created through unchecked `model_copy(update=...)` paths.
- Exact specification defaults for wink clicks, finite temple-tap scroll, and continuous
  temple-hold scroll.
- A pure binding manager with trigger/start/end resolution and deep validation at activation
  boundaries.
- Atomic user-profile persistence under the roaming configuration directory.
- Windows-safe profile names, traversal protection, duplicate-JSON-key rejection,
  case-insensitive collision handling, exclusive random temporary files, symlink/reparse-point
  rejection, corrupt-file quarantine, unavailable-storage recovery, and deterministic listing.
- A platform-neutral `InputExecutor` protocol and reusable in-memory test fake with held-state
  tracking plus reverse-order, best-effort, idempotent `release_all()` behavior.

## Safety decisions

- The built-in Default profile is immutable and exists in code rather than user JSON.
- Missing, ambiguous, corrupt, or invalid user profiles recover to a complete all-disabled
  profile. They never fall back to active default clicks or scroll actions.
- `mouse_scroll_continuous` and `mouse_down` are accepted only for temple holds that guarantee
  an end lifecycle event.
- Hold-end resolution never reads a new action. The future dispatcher must stop the owner
  captured at hold-start, even if the active profile changes mid-hold.
- Shell commands, processes, arbitrary key names, and arbitrary action types are not part of
  the action union.
- The fake executor contains no Win32, `ctypes`, automation-library, Qt, timer, or sleep code.

## Verification

```powershell
.\scripts\check.ps1
```

- Ruff format: 76 files already formatted.
- Ruff lint: all checks passed.
- Mypy strict: no issues in 76 source files.
- Pytest: 268 passed in 7.84 seconds.
- Focused action/binding/profile/input/config suite: 100 passed in 2.38 seconds.
- Both native Windows symlink/reparse regression cases ran successfully; no permission-based
  skips were reported.

## Known limitations

- Binding profiles are not yet selectable or editable in the UI.
- Gesture events are not yet sent to a dispatcher or executor.
- The fake executor proves only the primitive protocol boundary; all action variants will be
  dispatched through it in the next iteration.
- Continuous scheduling, exception containment, tracking lifecycle callbacks, and global
  release-all orchestration are not implemented yet.
- There is deliberately no Windows `SendInput` backend in this iteration.

## Next task

Implement a framework-independent, poll-driven action dispatcher using only the fake executor.
It must provide at-most-once one-shot dispatch, stable per-side continuous ownership,
no-catch-up scheduling, exception-to-fault behavior, and release-all handling for pause,
failure, profile change, and shutdown before any Windows backend is introduced.
