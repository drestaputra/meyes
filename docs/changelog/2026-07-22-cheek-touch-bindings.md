# Configurable cheek-touch bindings

Date: 2026-07-22

## Summary

Added independent left- and right-cheek touch gestures across the local vision, semantic event,
binding, dispatcher, and Diagnostics layers. Both entries are intentionally `Disabled` in the
built-in Default profile, so installing or upgrading MEYES cannot introduce a new click action.

## Added

- Symmetric MediaPipe Face Mesh cheek anchor groups: right `50/101/205` and left `280/330/425`.
- Same-side index-fingertip distance normalized by the already measured face width.
- Independent cheek proximity hysteresis using the existing validated face-touch thresholds and
  freshness timeout.
- A release-triggered cheek-touch state machine that requires fresh Far evidence before arming,
  emits once per stable interaction, applies cooldown, and resets without output on tracking loss.
- `LEFT_CHEEK_TOUCH` and `RIGHT_CHEEK_TOUCH` semantic events, binding rows, presentation labels,
  ordering channels, fake/native dispatch support, and live Diagnostics states/ratios.

## Changed

- Complete binding profiles now contain eight logical gestures and use schema version 2.
- Complete schema-1 six-gesture profiles, including profiles that relied on the former implicit
  schema version, migrate with both new actions disabled.
- Profile creation, restore, import/export copy, and previews now describe eight bindings.

## Verification

- Ruff formatting and lint checks.
- Strict mypy validation across source and tests.
- Deterministic detector, geometry, profile migration, dispatcher, controller, and Qt UI tests.
- Full deterministic suite: `822 passed`.
- Documentation link and deterministic Windows icon verification passed.

## Known limitations

- Webcam angle, occlusion, and individual hand placement can change practical touch sensitivity;
  a representative physical-device tuning pass remains necessary.
- The new bindings do nothing until a user explicitly selects and saves an action.

## Next task

Run a user-present camera validation for both cheeks, tune thresholds only from recorded evidence,
and verify deliberate cheek touches remain distinct from nearby temple gestures.
