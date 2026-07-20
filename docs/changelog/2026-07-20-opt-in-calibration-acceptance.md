# 2026-07-20 - Opt-in calibration acceptance

## Summary

Added a fail-closed acceptance boundary around volatile calibration results. MEYES now evaluates
RMSE, mean error, maximum error, and holdout count only when all four limits are explicitly
configured. With the safe defaults, no thresholds are invented and Calibration reports
`Review Required`. Neither an accepted nor an unaccepted mapper is persisted or activated.

## Added

- Immutable acceptance-policy, decision-state, and transparent rejection-reason contracts.
- All-or-none optional calibration limits in the validated application configuration.
- `Review Required`, `Accepted`, and `Rejected` outcomes in the Calibration UI.
- An `accepted_fit_result` boundary that returns a mapper only after every configured limit passes.
- Explicit final progress text showing `9 / 9 points complete` instead of resetting the target
  sample counter after completion.
- Domain, configuration, controller, and Qt regression coverage for review, acceptance, rejection,
  invalid limits, incomplete policy configuration, and legacy schema-one defaults.

## Safety and quality decisions

- All four acceptance limits default to unset because no representative physical-device benchmark
  has established defensible product thresholds.
- Partial policy configuration is invalid; the application cannot silently evaluate only the most
  convenient metric.
- Every missed configured limit is reported rather than stopping at the first failure.
- `fit_result` remains available only for volatile metrics and diagnostics;
  `accepted_fit_result` is the stricter contract for any future consumer.
- Even policy acceptance does not persist, activate, clamp, smooth, convert, or send a pointer
  position.

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m ruff check src\meyes tests\unit\test_calibration_acceptance.py tests\unit\test_config_manager.py tests\unit\test_calibration_ui.py
.\.venv\Scripts\python.exe -m mypy src\meyes\calibration\acceptance.py src\meyes\config\models.py src\meyes\ui\calibration_controller.py src\meyes\ui\calibration_page.py src\meyes\ui\main_window.py tests\unit\test_calibration_acceptance.py tests\unit\test_config_manager.py tests\unit\test_calibration_ui.py
.\.venv\Scripts\python.exe -m pytest -q tests\unit\test_calibration_acceptance.py tests\unit\test_config_manager.py tests\unit\test_calibration_ui.py
```

- Focused Ruff and strict mypy: passed.
- Focused pytest: 37 passed in 1.15 seconds.

Full repository gate:

- Ruff format: 117 files already formatted.
- Ruff lint: passed.
- Strict mypy: passed for 117 source files.
- Native Windows pytest: 612 passed in 19.75 seconds.

## Visual QA

- Rendered the `Review Required` completion state at 1000 x 720 on the native Windows Qt backend.
- Minimum page hint was 618 x 678; the new acceptance row, holdout metrics, target grid, and action
  controls remained readable without overlap.

## Known limitations

- No shipped acceptance limits exist until representative hardware and user-session evidence is
  collected.
- Limits currently require configuration-file editing; there is no settings UI for them.
- The mapper is memory-only and cannot control the pointer.
- Full-screen target presentation, head-pose compensation, adaptive smoothing, reach validation,
  persistence/recovery, and multi-monitor mapping remain pending.

## Next task

Build the distraction-free full-screen nine-point target presentation while preserving Escape,
tracking-loss, navigation, Live Input, and shutdown cancellation semantics.
