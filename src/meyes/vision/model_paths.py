"""Resolve local vision model assets without network access at runtime."""

from __future__ import annotations

import os
from pathlib import Path

FACE_LANDMARKER_ENV = "MEYES_FACE_LANDMARKER_MODEL"
FACE_LANDMARKER_FILENAME = "face_landmarker.task"


def face_landmarker_model_path() -> Path:
    """Return the configured or repository-local face landmarker model."""
    configured = os.environ.get(FACE_LANDMARKER_ENV)
    if configured:
        path = Path(configured).expanduser().resolve()
    else:
        project_root = Path(__file__).resolve().parents[3]
        path = project_root / "resources" / "models" / FACE_LANDMARKER_FILENAME
    if not path.is_file():
        raise FileNotFoundError(
            f"Face landmarker model not found at {path}. "
            f"Set {FACE_LANDMARKER_ENV} to a local model path."
        )
    return path
