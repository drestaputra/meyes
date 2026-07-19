"""Capture metric tests."""

from __future__ import annotations

import pytest

from meyes.camera.metrics import FrameRateMeter


def test_frame_rate_uses_monotonic_sample_window() -> None:
    meter = FrameRateMeter(window_size=4)

    assert meter.tick(10.0) == 0.0
    assert meter.tick(10.1) == pytest.approx(10.0)
    assert meter.tick(10.2) == pytest.approx(10.0)


def test_frame_rate_rejects_invalid_window_size() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        FrameRateMeter(window_size=1)
