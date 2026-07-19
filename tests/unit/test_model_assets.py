"""Bundled vision model integrity tests."""

from __future__ import annotations

import hashlib

from meyes.vision.model_paths import face_landmarker_model_path, hand_landmarker_model_path

EXPECTED_FACE_LANDMARKER_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
EXPECTED_HAND_LANDMARKER_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"


def test_face_landmarker_model_is_present_and_verified() -> None:
    model_path = face_landmarker_model_path()

    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()

    assert model_path.stat().st_size == 3_758_596
    assert digest == EXPECTED_FACE_LANDMARKER_SHA256


def test_hand_landmarker_model_is_present_and_verified() -> None:
    model_path = hand_landmarker_model_path()

    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()

    assert model_path.stat().st_size == 7_819_105
    assert digest == EXPECTED_HAND_LANDMARKER_SHA256
