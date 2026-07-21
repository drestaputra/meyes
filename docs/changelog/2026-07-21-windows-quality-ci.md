# 2026-07-21 - Windows quality CI

## Summary

Added repository-hosted Windows verification for pushes to `main`, pull requests, and deliberate
manual runs. The workflow reuses the exact safe judge command rather than defining a second gate.

## Added

- A least-privilege GitHub Actions workflow with read-only repository contents permission,
  per-ref concurrency cancellation, and a bounded job timeout.
- Full-SHA pins for `actions/checkout` v6.0.2 and `astral-sh/setup-uv` v8.1.0.
- A pinned uv 0.11.29 and CPython 3.11 environment running `scripts/judge_verify.ps1` on
  `windows-latest`.

## Verification

- Full action tag SHAs were resolved from their official GitHub repositories before authoring.
- The workflow file and safe judge script are required by local submission preflight.
- Local `scripts/check.ps1` and `scripts/submission_preflight.ps1 -AllowDirty` must pass before push.
- The first remote workflow run must pass before this iteration is considered externally verified.

## Known limitations

- CI exercises fake camera/model boundaries plus isolated installed-wheel integrity; it does not
  provide a camera, arm native input, produce a standalone package, or replace clean-machine QA.
- `windows-latest` is GitHub's managed image rather than the documented representative end-user
  hardware matrix.

## Next task

Observe the first remote workflow run, retain its exact conclusion, and fix any runner-only drift.
