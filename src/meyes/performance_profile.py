"""Safe synthetic performance probe for the packaged local model adapters."""

from __future__ import annotations

import json
import math
import platform
import statistics
import time
from collections.abc import Callable
from typing import Protocol, TypedDict

import numpy as np

from meyes import __version__
from meyes.camera.models import FramePacket


class ProfileBackend(Protocol):
    """Minimal model adapter surface needed by the synthetic probe."""

    def process(self, packet: FramePacket) -> object: ...

    def close(self) -> None: ...


BackendFactory = Callable[[], ProfileBackend]
Clock = Callable[[], float]


class PipelineProfile(TypedDict):
    name: str
    initialization_ms: float | None
    first_inference_ms: float | None
    warm_inference_median_ms: float | None
    warm_inference_p95_ms: float | None
    warm_inference_max_ms: float | None
    close_ms: float | None
    measured_iterations: int
    discarded_warmup_iterations: int
    error: str | None


class SafePerformanceProfile(TypedDict):
    schema_version: int
    meyes_version: str
    python_version: str
    platform: str
    scope: str
    frame: dict[str, int | str]
    iterations_per_pipeline: int
    warmup_iterations: int
    pipelines: list[PipelineProfile]
    overall_pass: bool
    safety: str
    limitations: list[str]


def _face_factory() -> ProfileBackend:
    from meyes.vision.face_landmarker import MediaPipeFaceLandmarker

    return MediaPipeFaceLandmarker()


def _hand_factory() -> ProfileBackend:
    from meyes.vision.hand_landmarker import MediaPipeHandLandmarker

    return MediaPipeHandLandmarker()


def _milliseconds(start: float, end: float) -> float:
    return round((end - start) * 1000.0, 3)


def _nearest_rank_p95(values: list[float]) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def _measure_pipeline(
    name: str,
    factory: BackendFactory,
    frame: np.ndarray,
    *,
    iterations: int,
    warmup: int,
    clock: Clock,
) -> PipelineProfile:
    backend: ProfileBackend | None = None
    initialization_ms: float | None = None
    close_ms: float | None = None
    durations: list[float] = []
    error: str | None = None
    try:
        started = clock()
        backend = factory()
        initialization_ms = _milliseconds(started, clock())
        for index in range(iterations):
            packet = FramePacket(
                sequence=index + 1,
                capture_timestamp=(index + 1) / 30.0,
                frame=frame,
            )
            started = clock()
            backend.process(packet)
            durations.append(_milliseconds(started, clock()))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        if backend is not None:
            try:
                started = clock()
                backend.close()
                close_ms = _milliseconds(started, clock())
            except Exception as exc:
                close_error = f"{type(exc).__name__}: {exc}"
                error = close_error if error is None else f"{error}; close failed: {close_error}"

    warm_durations = durations[warmup:]
    return {
        "name": name,
        "initialization_ms": initialization_ms,
        "first_inference_ms": durations[0] if durations else None,
        "warm_inference_median_ms": (
            round(statistics.median(warm_durations), 3) if warm_durations else None
        ),
        "warm_inference_p95_ms": (
            round(_nearest_rank_p95(warm_durations), 3) if warm_durations else None
        ),
        "warm_inference_max_ms": round(max(warm_durations), 3) if warm_durations else None,
        "close_ms": close_ms,
        "measured_iterations": len(durations),
        "discarded_warmup_iterations": min(warmup, len(durations)),
        "error": error,
    }


def collect_safe_performance_profile(
    *,
    iterations: int = 12,
    warmup: int = 2,
    width: int = 640,
    height: int = 480,
    face_factory: BackendFactory = _face_factory,
    hand_factory: BackendFactory = _hand_factory,
    clock: Clock = time.perf_counter,
) -> SafePerformanceProfile:
    """Measure model adapters on one in-memory blank frame without hardware or Qt."""
    if iterations < 3:
        raise ValueError("iterations must be at least 3")
    if warmup < 1 or warmup >= iterations:
        raise ValueError("warmup must be at least 1 and less than iterations")
    if width < 1 or height < 1:
        raise ValueError("frame dimensions must be positive")

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    pipelines = [
        _measure_pipeline(
            "face_landmarker",
            face_factory,
            frame,
            iterations=iterations,
            warmup=warmup,
            clock=clock,
        ),
        _measure_pipeline(
            "hand_landmarker",
            hand_factory,
            frame,
            iterations=iterations,
            warmup=warmup,
            clock=clock,
        ),
    ]
    overall_pass = all(
        item["error"] is None and item["measured_iterations"] == iterations for item in pipelines
    )
    return {
        "schema_version": 1,
        "meyes_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "scope": "Sequential local model adapters on an in-memory blank BGR frame.",
        "frame": {"width": width, "height": height, "channels": 3, "content": "all zeros"},
        "iterations_per_pipeline": iterations,
        "warmup_iterations": warmup,
        "pipelines": pipelines,
        "overall_pass": overall_pass,
        "safety": (
            "No GUI, camera, live image, emergency hotkey, or operating-system input was activated."
        ),
        "limitations": [
            (
                "Blank-frame timing is not evidence of live face/hand accuracy, latency, or "
                "throughput."
            ),
            (
                "The two adapters are measured sequentially; production initializes them on "
                "separate workers."
            ),
            (
                "Results are host-, load-, runtime-, and dependency-specific and must not be "
                "generalized."
            ),
            "MediaPipe dependency network behavior remains subject to the boundary in PRIVACY.md.",
        ],
    }


def print_safe_performance_profile() -> int:
    """Print the synthetic profile as JSON and fail if either adapter could not complete."""
    result = collect_safe_performance_profile()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1
