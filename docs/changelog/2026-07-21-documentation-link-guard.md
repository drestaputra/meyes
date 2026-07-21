# 2026-07-21 - Documentation link guard

## Summary

Added a repeatable repository-wide check for local targets referenced by tracked Markdown files.

## Added

- `scripts/verify_docs.ps1` enumerates Markdown through Git, checks inline and reference-style local
  links, decodes URL-escaped paths, and rejects missing targets.
- Resolved paths must remain inside the repository; web URLs, other URI schemes, and same-page
  anchors are intentionally outside this local-file check.
- The normal quality gate and submission preflight now run the documentation verifier.

## Verification

- Run `./scripts/verify_docs.ps1` from the repository.
- Run `./scripts/check.ps1` for the complete deterministic gate.
- Run `./scripts/submission_preflight.ps1 -AllowDirty` before committing the iteration.

## Known limitations

- The guard verifies local file/directory existence, not remote URL availability or Markdown
  heading-anchor spelling.
- Human review remains required for the meaning, currency, and truthfulness of submission copy.

## Next task

Audit the remaining repository/submission claims for stale counts and exact-revision drift.
