# 2026-07-21 - Submission scope refresh

## Summary

Updated judge and Devpost copy after multiple Phase 6 features moved from roadmap to implemented
scope. The submission preflight now rejects the two exact stale roadmap phrases found by the audit.

## Corrections

- Removed tray controls from the judge guide's not-implemented list.
- Removed first-run setup from Devpost What's next.
- Added bounded first-run, Camera/Sensitivity, Privacy, keyboard navigation, system-theme High
  Contrast fallback, and conditional tray behavior to current-scope copy.
- Kept standalone executable/installer, enabled High Contrast evidence, 125%/150% scaling evidence,
  broad reach, and clean-machine live checks explicitly pending.

## Verification

- PowerShell parser validation passed.
- Dirty-tree live-remote preflight passed and direct search found neither stale phrase.
- Clean live-remote preflight is run after push.
