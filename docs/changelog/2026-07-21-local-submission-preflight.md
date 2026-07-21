# 2026-07-21 - Local submission preflight

## Summary

Added a non-mutating PowerShell preflight for the local, automatable portion of Devpost readiness.
It deliberately does not convert human attestations or external service state into a false pass.

## Checks

- Git is available, current branch is `main`, and origin points to `drestaputra/meyes`.
- The worktree is clean unless development validation explicitly uses `-AllowDirty`.
- README, judge guide, privacy, license, third-party notices, lockfile, submission record/draft, and
  model provenance are present and tracked.
- The license and README retain required local evidence text.
- `-RunFullCheck` invokes the frozen-lock native Windows quality gate.

## Explicit non-checks

The script always lists eligibility/rights/category attestations, judge repository access, live
clean-user testing, public video, `/feedback` Session ID, authenticated fields, and final Devpost
submission state as human/external blockers.

## Verification

- PowerShell parser validation passed for every script in `scripts/`.
- Development execution with `-AllowDirty` passed all local invariants.
- `-AllowDirty -RunFullCheck` passed Ruff formatting, Ruff lint, strict mypy, and all 740 tests on
  native Windows Qt.
- A clean-worktree run remains intentionally scheduled after this script lands on `main`.
