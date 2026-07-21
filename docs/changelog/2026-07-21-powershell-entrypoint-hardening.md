# 2026-07-21 - PowerShell entry-point hardening

## Summary

Hardened all developer and judge PowerShell entry points after fresh-clone verification found that
`uv` was available only through `python -m uv` on the host. Scripts now share one fail-fast resolver
and use the committed lockfile in frozen mode.

## Changed

- Added a shared resolver that prefers a direct `uv` launcher and falls back to `python -m uv` only
  after verifying the module is importable.
- Added one actionable prerequisite failure when neither route exists.
- Made run, sync, test, full check, and display-evidence capture use the shared helper.
- Added `--frozen` to every project execution/sync path so scripts cannot silently change the lock.
- Removed automatic `QT_QPA_PLATFORM=offscreen`; native Windows Qt is now the default, while CI or
  callers may still set a platform explicitly.
- Converted nonzero native exit codes into immediate PowerShell failures instead of continuing.

## Verification

- Every `.ps1` file passed PowerShell parser validation.
- The host fallback resolved to `python -m uv` and reported uv 0.11.29.
- The isolated direct-launcher path ran 8 display-evidence tests successfully.
- `scripts/check.ps1` passed on native Windows Qt: 140 formatted files, Ruff lint, strict mypy, and
  `740 passed in 24.28s`.

## Next task

Keep scripts stable for judge use and focus remaining time on human-controlled live QA, video, and
submission fields rather than broadening runtime scope.
