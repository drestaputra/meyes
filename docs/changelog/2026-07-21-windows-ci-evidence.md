# 2026-07-21 - Windows CI evidence

## Summary

Recorded the first fully passing remote Windows quality run after correcting the two portability
findings from the initial run.

## Evidence

- Exact revision: `c91c3a175402fff6ed7b3397630feed4e568da55`.
- GitHub Actions run `29848753863`, job `88695946333`: success.
- Tracked documentation, Ruff, strict mypy across 158 source files, all 787 tests, isolated wheel
  installation, and installed asset integrity passed.
- The native Windows Qt platform remained enabled; the workflow did not activate camera or OS input.

Full evidence: [`docs/evidence/ci/2026-07-21.md`](../evidence/ci/2026-07-21.md).

## Known limitations

The managed runner does not replace physical hardware, accessibility, standalone delivery, signing,
or clean-machine acceptance evidence.

## Next task

Continue the next safe, unblocked MVP-readiness iteration while preserving the now-active remote
quality gate.
