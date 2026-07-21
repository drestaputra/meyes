"""Safe synthetic performance-profile tests without MediaPipe or hardware."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from meyes.__main__ import main
from meyes.camera.models import FramePacket
from meyes.performance_profile import collect_safe_performance_profile


class StepClock:
    def __init__(self, step: float = 0.001) -> None:
        self._value = 0.0
        self._step = step

    def __call__(self) -> float:
        current = self._value
        self._value += self._step
        return current


class RecordingBackend:
    def __init__(self) -> None:
        self.packets: list[FramePacket] = []
        self.closed = False

    def process(self, packet: FramePacket) -> object:
        self.packets.append(packet)
        return object()

    def close(self) -> None:
        self.closed = True


def test_profile_is_bounded_machine_readable_and_hardware_free() -> None:
    face = RecordingBackend()
    hand = RecordingBackend()

    result = collect_safe_performance_profile(
        iterations=5,
        warmup=2,
        width=8,
        height=6,
        face_factory=lambda: face,
        hand_factory=lambda: hand,
        clock=StepClock(),
    )

    assert result["overall_pass"] is True
    assert result["frame"] == {"width": 8, "height": 6, "channels": 3, "content": "all zeros"}
    assert "No GUI, camera" in result["safety"]
    assert [item["measured_iterations"] for item in result["pipelines"]] == [5, 5]
    assert all(item["initialization_ms"] == 1.0 for item in result["pipelines"])
    assert all(item["warm_inference_median_ms"] == 1.0 for item in result["pipelines"])
    assert face.closed and hand.closed
    assert all(packet.frame.shape == (6, 8, 3) for packet in [*face.packets, *hand.packets])
    assert all(np.count_nonzero(packet.frame) == 0 for packet in [*face.packets, *hand.packets])


class FailingBackend(RecordingBackend):
    def process(self, packet: FramePacket) -> object:
        super().process(packet)
        raise RuntimeError("synthetic failure")


def test_profile_contains_pipeline_failure_and_still_closes_both_backends() -> None:
    face = FailingBackend()
    hand = RecordingBackend()

    result = collect_safe_performance_profile(
        iterations=3,
        warmup=1,
        face_factory=lambda: face,
        hand_factory=lambda: hand,
        clock=StepClock(),
    )

    assert result["overall_pass"] is False
    assert result["pipelines"][0]["error"] == "RuntimeError: synthetic failure"
    assert result["pipelines"][1]["error"] is None
    assert face.closed and hand.closed


@pytest.mark.parametrize(
    ("iterations", "warmup", "width", "height", "message"),
    [
        (2, 1, 640, 480, "iterations"),
        (3, 0, 640, 480, "warmup"),
        (3, 3, 640, 480, "warmup"),
        (3, 1, 0, 480, "dimensions"),
        (3, 1, 640, -1, "dimensions"),
    ],
)
def test_profile_rejects_unbounded_or_invalid_parameters(
    iterations: int,
    warmup: int,
    width: int,
    height: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        collect_safe_performance_profile(
            iterations=iterations,
            warmup=warmup,
            width=width,
            height=height,
            face_factory=RecordingBackend,
            hand_factory=RecordingBackend,
        )


def test_profile_cli_route_does_not_start_desktop_application() -> None:
    with patch("meyes.performance_profile.print_safe_performance_profile", return_value=0) as run:
        assert main(["--profile-safe"]) == 0

    run.assert_called_once_with()
