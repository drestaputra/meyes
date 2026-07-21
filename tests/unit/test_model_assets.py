"""Bundled vision model integrity tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from meyes.install_diagnostics import (
    EXPECTED_FACE_LANDMARKER_SHA256,
    EXPECTED_HAND_LANDMARKER_SHA256,
)
from meyes.vision import model_paths
from meyes.vision.model_paths import face_landmarker_model_path, hand_landmarker_model_path


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


def test_packaged_model_is_preferred_over_source_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packaged = tmp_path / "packaged"
    source = tmp_path / "source"
    packaged.mkdir()
    source.mkdir()
    packaged_model = packaged / model_paths.FACE_LANDMARKER_FILENAME
    source_model = source / model_paths.FACE_LANDMARKER_FILENAME
    packaged_model.write_bytes(b"packaged")
    source_model.write_bytes(b"source")
    monkeypatch.delenv(model_paths.FACE_LANDMARKER_ENV, raising=False)
    monkeypatch.setattr(model_paths, "_PACKAGED_MODELS_DIR", packaged)
    monkeypatch.setattr(model_paths, "_SOURCE_MODELS_DIR", source)

    assert model_paths.face_landmarker_model_path() == packaged_model


def test_source_model_is_used_when_packaged_asset_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packaged = tmp_path / "packaged"
    source = tmp_path / "source"
    source.mkdir()
    source_model = source / model_paths.HAND_LANDMARKER_FILENAME
    source_model.write_bytes(b"source")
    monkeypatch.delenv(model_paths.HAND_LANDMARKER_ENV, raising=False)
    monkeypatch.setattr(model_paths, "_PACKAGED_MODELS_DIR", packaged)
    monkeypatch.setattr(model_paths, "_SOURCE_MODELS_DIR", source)

    assert model_paths.hand_landmarker_model_path() == source_model
