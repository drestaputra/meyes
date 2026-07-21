# 2026-07-22 - Camera-start calibration onboarding

## Summary

Connected a successful camera start to the existing Calibration workflow when no accepted,
current-display calibration is active.

## Changed

- `Stopped/Starting -> Running` selects Calibration, explains the guided nine-point flow, and
  focuses the Start button.
- Collection remains deliberate: no fullscreen presentation or sample capture starts automatically.
- Camera resume does not repeat the redirect, and an active recovered/saved/volatile accepted
  provisioning leaves the user's current page unchanged.
- Safe Mode and volatile Live Input consent remain unchanged.

## Verification

- MainWindow tests cover missing calibration, focus/instruction state, Safe Mode invariants, no
  resume redirect, and usable startup-recovered calibration.
- The full local gate passed: documentation and ICO verification, Ruff, strict mypy across 158
  typed source/test files, and all 789 tests on native Windows Qt.
- Remote Windows CI must pass on the exact pushed revision before completing the iteration.

## Known limitations

The onboarding cannot turn a `Review Required` fit into an accepted calibration. Evidence-backed
acceptance policy and representative physical reach validation remain separate requirements.

## Next task

Validate the transition with a physical camera and record whether the onboarding copy remains clear
at 100%, 125%, and 150% Windows display scaling.
