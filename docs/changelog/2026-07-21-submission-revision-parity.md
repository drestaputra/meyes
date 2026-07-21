# 2026-07-21 - Submission revision parity

## Summary

Hardened the local submission preflight so the reviewed revision cannot silently differ from the
locally tracked or live GitHub `main` branch. Removed a stale-revision reminder from the Devpost
copy in favor of a reproducible exact-revision verification command.

## Changes

- Require local `HEAD` to match the configured `origin/main` upstream-tracking revision.
- Add opt-in `-VerifyRemote` comparison against the live `refs/heads/main` SHA.
- Reject unresolved `Update this number`, `TODO`, `TBD`, or `Untitled` markers in the Devpost draft.
- Report the audited revision in successful preflight output.
- Keep remote access read-only and keep all authenticated submission actions outside the script.

## Verification

- PowerShell parser validation is required for every script.
- Dirty-tree development runs cover local and live-remote parity before commit.
- A clean-tree live-remote run is performed after the iteration is pushed.
