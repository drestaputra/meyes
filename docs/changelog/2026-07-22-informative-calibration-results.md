# 2026-07-22 - Informative calibration results

## Summary

Made the existing nine-point quadratic calibration easier to understand without weakening its
evidence or safety boundaries.

## Changed

- The full-screen completion state now shows a centered result card instead of an empty canvas.
- The card names Accepted, Rejected, Review Required, or Fit failed in plain language.
- Available RMSE, mean error, maximum error, and holdout sample count appear in a readable block.
- The result explains why pointer activation is allowed or blocked and directs the user back to the
  Calibration page for details or retry.
- Capture, Next, and Cancel disappear after completion; Return to Calibration becomes the single
  primary action.
- Escape and window close preserve a completed volatile fit instead of discarding it.
- Point-start wording now clarifies that Space is pressed once and stable samples then collect
  automatically.
- Binding previews spell out scroll direction instead of exposing only signed wheel deltas.

The nine targets remain because the current quadratic mapper has six coefficients and relies on the
extra spatial coverage for rank and holdout validation. A five-point quick flow would require a
separate affine model, acceptance evidence, persistence compatibility, and representative hardware
validation rather than merely hiding four targets.

## Scroll mapping verification

- Right-temple tap scrolls up by three steps; hold scrolls up continuously by two steps per tick.
- Left-temple tap scrolls down by three steps; hold scrolls down continuously by two steps per tick.
- The sign convention matches Windows wheel input: positive is up and negative is down.

## Verification

- Focused calibration/binding tests cover the result card, metrics, relevant control visibility,
  completion-safe Escape, direction labels, and exact Default tap/hold signs.
- Native 900x640 and 1200x760 result renders were readable without clipping.
- The full local gate passed: documentation and ICO verification, Ruff, strict mypy across 160 typed
  source/test files, and all 794 tests on native Windows Qt.
- Exact-revision remote Windows CI must pass before completing the iteration.

## Known limitations

Default acceptance remains Review Required until representative physical-device evidence supports a
complete four-limit policy. This UX change does not invent thresholds or enable pointer output.

## Next task

Evaluate a separately modeled affine quick-calibration experiment only after the nine-point path has
representative physical reach and repeatability evidence.
