# MEYES Dated Changelog

This directory contains detailed development records for individual implementation batches. The root `CHANGELOG.md` will remain the concise release-level summary once application development begins.

## File naming

Use:

```text
YYYY-MM-DD-short-description.md
```

Examples:

```text
2026-07-19-planning-baseline.md
2026-07-22-camera-worker.md
2026-07-24-camera-recovery-tests.md
```

Rules:

- Use the local project date in `YYYY-MM-DD` format.
- Use lowercase kebab-case for the description.
- Keep the description short and specific.
- If more than one independent entry has the same description on one date, add a numeric suffix such as `-02`.
- Do not rename historical entries after they have been included in a commit or release.

## Required entry structure

Each file should contain:

1. summary;
2. added, changed, fixed, or removed items as applicable;
3. verification commands and results;
4. known limitations;
5. exact next task.

Use [`2026-07-19-planning-baseline.md`](./2026-07-19-planning-baseline.md) as the initial example.
