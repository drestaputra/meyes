"""Resolve local vision model assets without network access at runtime."""

from __future__ import annotations

import os
from pathlib import Path

FACE_LANDMARKER_ENV = "MEYES_FACE_LANDMARKER_MODEL"
FACE_LANDMARKER_FILENAME = "face_landmarker.task"
HAND_LANDMARKER_ENV = "MEYES_HAND_LANDMARKER_MODEL"
HAND_LANDMARKER_FILENAME = "hand_landmarker.task"
_PACKAGED_MODELS_DIR = Path(__file__).resolve().parents[1] / "resources" / "models"
_SOURCE_MODELS_DIR = Path(__file__).resolve().parents[3] / "resources" / "models"


def _resolve_model_path(*, environment_name: str, filename: str, label: str) -> Path:
    configured = os.environ.get(environment_name)
    candidates: tuple[Path, ...]
    if configured:
        candidates = (Path(configured).expanduser().resolve(),)
    else:
        candidates = (
            _PACKAGED_MODELS_DIR / filename,
            _SOURCE_MODELS_DIR / filename,
        )

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        f"{label} model not found. Searched: {searched}. "
        f"Set {environment_name} to a local model path."
    )


def face_landmarker_model_path() -> Path:
    """Return the configured, packaged, or source-tree face landmarker model."""
    return _resolve_model_path(
        environment_name=FACE_LANDMARKER_ENV,
        filename=FACE_LANDMARKER_FILENAME,
        label="Face landmarker",
    )


def hand_landmarker_model_path() -> Path:
    """Return the configured, packaged, or source-tree hand landmarker model."""
    return _resolve_model_path(
        environment_name=HAND_LANDMARKER_ENV,
        filename=HAND_LANDMARKER_FILENAME,
        label="Hand landmarker",
    )
