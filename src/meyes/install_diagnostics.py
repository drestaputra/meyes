"""Standard-library-only installed artifact diagnostics."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from meyes import __version__
from meyes.vision.model_paths import face_landmarker_model_path, hand_landmarker_model_path

EXPECTED_FACE_LANDMARKER_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
EXPECTED_HAND_LANDMARKER_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"


class ModelDiagnostic(TypedDict):
    name: str
    path: str
    size: int
    sha256: str
    verified: bool
    error: str | None


class InstallDiagnostic(TypedDict):
    meyes_version: str
    python_version: str
    platform: str
    supported_python: bool
    supported_platform: bool
    models: list[ModelDiagnostic]
    overall_pass: bool
    safety: str


def _model_diagnostic(
    *,
    name: str,
    resolver: Callable[[], Path],
    expected_size: int,
    expected_sha256: str,
) -> ModelDiagnostic:
    try:
        path = resolver()
        size = path.stat().st_size
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        verified = size == expected_size and digest == expected_sha256
        error = None if verified else "Model size or SHA-256 does not match the recorded asset."
        return {
            "name": name,
            "path": str(path),
            "size": size,
            "sha256": digest,
            "verified": verified,
            "error": error,
        }
    except OSError as exc:
        return {
            "name": name,
            "path": "",
            "size": 0,
            "sha256": "",
            "verified": False,
            "error": str(exc),
        }


def collect_install_diagnostics() -> InstallDiagnostic:
    """Collect deterministic install facts without importing GUI or native-input modules."""
    models = [
        _model_diagnostic(
            name="face_landmarker.task",
            resolver=face_landmarker_model_path,
            expected_size=3_758_596,
            expected_sha256=EXPECTED_FACE_LANDMARKER_SHA256,
        ),
        _model_diagnostic(
            name="hand_landmarker.task",
            resolver=hand_landmarker_model_path,
            expected_size=7_819_105,
            expected_sha256=EXPECTED_HAND_LANDMARKER_SHA256,
        ),
    ]
    supported_python = sys.version_info[:2] == (3, 11)
    supported_platform = sys.platform == "win32"
    return {
        "meyes_version": __version__,
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "supported_python": supported_python,
        "supported_platform": supported_platform,
        "models": models,
        "overall_pass": supported_python
        and supported_platform
        and all(model["verified"] for model in models),
        "safety": "No GUI, camera, model inference, or operating-system input was activated.",
    }


def print_install_diagnostics() -> int:
    """Print machine-readable diagnostics and return nonzero on an unsupported install."""
    result = collect_install_diagnostics()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["overall_pass"] else 1
