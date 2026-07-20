# 2026-07-20 - Safe profile transfer

## Summary

Added user-facing import and export for complete MEYES binding profiles. Imported files are bounded,
strictly validated, and always created as new inactive profiles. Export reads a valid snapshot
without mutating repository recovery state or either runtime dispatcher.

## Added

- A dedicated import/export panel in **Profiles** with native Windows open/save dialogs.
- Import of local UTF-8 `.json` files up to 256 KiB.
- Recursive duplicate-key rejection, excessive-nesting rejection, and full Pydantic schema/action
  validation before any catalog write.
- Optional Windows-safe local rename for resolving imported `Default` or catalog collisions.
- Strict repository reads for export without fallback, invalid-file backup, or runtime mutation.
- Exclusive creation for new exports and temp-file plus `os.replace` for confirmed overwrite.
- Inactive-only import semantics and export support for Default, active, or inactive profiles.
- Inline success/error feedback, accessible controls, bounded path display, and narrow-width layout
  coverage.

## Safety decisions

- Import never overwrites a local profile and never activates the imported snapshot.
- Invalid, oversized, duplicate-key, deeply nested, non-UTF-8, non-JSON, directory, symlink, and
  reparse-point inputs fail before catalog mutation.
- Export rejects non-JSON destinations, missing/non-directory parents, symlink/reparse destinations,
  and unconfirmed collisions.
- A failed atomic overwrite keeps the original destination and removes its temporary file.
- File-dialog entry disarms Live Input first. If native release fails, the dialog is not opened.
  This is required because Qt documents that the native Windows file dialog runs a blocking modal
  loop that does not dispatch `QTimer` events.
- The selected import path exists only in widget memory and is cleared after successful import.
- Import/export does not persist the active-profile preference, activate a profile, or dispatch a
  fake/native action.

## Official references

- [Qt for Python QFileDialog](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QFileDialog.html)
- [Python 3.11 pathlib](https://docs.python.org/3.11/library/pathlib.html)
- [Python 3.11 os.replace](https://docs.python.org/3.11/library/os.html#os.replace)

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes\bindings\transfer.py src\meyes\bindings\repository.py src\meyes\ui\profile_controller.py src\meyes\ui\profiles_page.py
.\.venv\Scripts\python.exe -m mypy src\meyes\bindings\transfer.py src\meyes\bindings\repository.py src\meyes\ui\profile_controller.py src\meyes\ui\profiles_page.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_profile_transfer.py tests\unit\test_binding_repository.py tests\unit\test_profile_controller.py tests\unit\test_profiles_page.py tests\unit\test_diagnostics_page.py tests\unit\test_main_window.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 106 passed in 5.41 seconds.

Full repository gate:

- Ruff format: 103 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 103 source files.
- Pytest: 519 passed in 21.26 seconds.

## Native QA

- Native Windows render: passed at 1200 × 760 with the full import/export panel visible, readable,
  horizontally contained, and keyboard-focusable inside the existing vertical scroll area.
- Safe Mode remained visible in the persistent bar; no hotkey was registered and no file dialog,
  camera, model backend, or `SendInput` call was activated by the render.

## Known limitations

- The transfer format is the existing schema-version-1 JSON snapshot; no migrations from future
  schema versions exist yet.
- The workflow transfers one profile per operation and does not support bundle archives.
- Native dialog behavior and path permissions ultimately depend on Windows and the selected
  filesystem.

## Next task

Continue to the next bounded Phase 4/5 task without weakening the guarded Live Input lifecycle.
