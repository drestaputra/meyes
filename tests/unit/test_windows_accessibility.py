"""Windows High Contrast preference boundary tests."""

from __future__ import annotations

from dataclasses import dataclass

from meyes.ui.windows_accessibility import windows_high_contrast_enabled


@dataclass
class FakeAccessibilityApi:
    enabled: bool = False
    error: OSError | None = None
    reads: int = 0

    def high_contrast_enabled(self) -> bool:
        self.reads += 1
        if self.error is not None:
            raise self.error
        return self.enabled


def test_high_contrast_probe_reports_enabled_and_disabled() -> None:
    enabled = FakeAccessibilityApi(enabled=True)
    disabled = FakeAccessibilityApi(enabled=False)

    assert windows_high_contrast_enabled(enabled) is True
    assert windows_high_contrast_enabled(disabled) is False
    assert enabled.reads == 1
    assert disabled.reads == 1


def test_high_contrast_probe_falls_back_without_mutating_on_native_failure() -> None:
    api = FakeAccessibilityApi(error=OSError("unavailable"))

    assert windows_high_contrast_enabled(api) is False
    assert api.reads == 1
