"""Bundled vision model integrity tests."""

from __future__ import annotations

import hashlib

from meyes.vision.model_paths import face_landmarker_model_path

EXPECTED_FACE_LANDMARKER_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"


def test_face_landmarker_model_is_present_and_verified() -> None:
    model_path = face_landmarker_model_path()

    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()

    assert model_path.stat().st_size == 3_758_596
    assert digest == EXPECTED_FACE_LANDMARKER_SHA256
