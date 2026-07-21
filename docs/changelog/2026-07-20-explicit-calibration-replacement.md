# 2026-07-20 - Explicit saved-calibration replacement

## Summary

Prevented a newly accepted calibration from automatically overwriting an existing saved envelope.
The new fit is provisioned only for the current session until the user types
`REPLACE SAVED CALIBRATION` exactly.

## Added

- Lifecycle tracking for whether an active saved envelope exists.
- A `Pending Replace` result that provisions the accepted fit without writing it.
- Exact-phrase replace controls on the Calibration page.
- Composition-root confirmation that releases Live Input before allowing replacement.
- Domain, page, and repository-backed composition tests proving the prior envelope remains intact
  until confirmation.

## Safety and data behavior

- Starting or completing calibration never deletes the prior saved envelope.
- A pending fit remains volatile and disappears on restart unless explicitly confirmed.
- Confirmation is case-sensitive and available only for a pending accepted fit.
- Failed Live Input release prevents the repository write.
- Successful replacement remains atomic and stores no raw gaze samples.

## Visual QA

Native Windows renders were inspected at 900 x 640 and 1200 x 760, at both top and bottom scroll
positions. The added controls remain fully accessible without overlap. A detected 6 px minimum-size
horizontal overflow was removed by tightening content margins, and the zero-horizontal-overflow
invariant is covered by a constrained-viewport regression.

## Verification

Focused Ruff format/lint, strict mypy, and `43 passed` completed first. The full repository gate
then passed: Ruff format and lint, strict mypy across 138 source files, and `728 passed`.

## Next task

Run the full deterministic gate, then add a permanent, bounded deleted-calibration backup cleanup
workflow before physical scaling-matrix evidence collection.
