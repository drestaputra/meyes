# 2026-07-21 - Windows CI portability fix

## Summary

Resolved both failures exposed by the first remote Windows quality run without weakening the
application gate or switching Qt tests to an offscreen backend.

## Fixed

- Forced LF checkout for the checksummed SVG icon so its committed byte digest remains identical
  when GitHub's Windows checkout applies platform line-ending behavior.
- Made calibration target-position assertions use the actual exposed widget width and height.
  Windows runners may clamp an ordinary 1000x800 test window to their available desktop area, while
  the product behavior correctly places targets at normalized coordinates of that actual area.

## Verification

- The first remote run `29848410870` reached 785 passing tests and exposed exactly two failures:
  icon byte digest and calibration presentation height assumptions.
- Run the focused icon/calibration tests locally, then the complete deterministic gate.
- Push the fix and require a passing remote Windows quality run on the exact fix commit.

## Known limitations

- This is deterministic runner portability evidence, not a human full-screen calibration pass.
- Physical 125%/150% scale, enabled High Contrast, camera, and native-input evidence remain pending.

## Next task

Record and link the first passing remote Windows workflow run, then resume the next unblocked MVP
readiness task.
