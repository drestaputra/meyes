"""Configuration persistence and recovery tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from meyes.config.manager import ConfigManager
from meyes.config.models import (
    AppConfig,
    AppSettings,
    CameraSettings,
    GestureSettings,
    TrackingSettings,
)
from meyes.util.paths import AppPaths


def test_missing_config_creates_safe_defaults(tmp_path: Path) -> None:
    manager = ConfigManager(AppPaths.under(tmp_path))

    result = manager.load()

    assert result.config == AppConfig()
    assert result.warning is None
    assert manager.config_path.exists()


def test_config_round_trip(tmp_path: Path) -> None:
    manager = ConfigManager(AppPaths.under(tmp_path))
    expected = AppConfig(camera=CameraSettings(camera_index=2, mirror=False))

    manager.save(expected)
    result = manager.load()

    assert result.config == expected


def test_corrupt_json_is_backed_up_and_replaced(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    paths.config_file.write_text("{not-json", encoding="utf-8")
    fixed_now = datetime(2026, 7, 19, 12, 30, tzinfo=UTC)
    manager = ConfigManager(paths, clock=lambda: fixed_now)

    result = manager.load()

    assert result.config == AppConfig()
    assert result.warning is not None
    assert result.recovered_from is not None
    assert result.recovered_from.name.startswith("config.invalid-20260719-123000")
    assert result.recovered_from.read_text(encoding="utf-8") == "{not-json"
    assert json.loads(paths.config_file.read_text(encoding="utf-8"))["schema_version"] == 1


def test_unknown_config_key_is_recovered(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    paths.ensure_directories()
    paths.config_file.write_text('{"schema_version": 1, "unexpected": true}', encoding="utf-8")
    manager = ConfigManager(paths)

    result = manager.load()

    assert result.warning is not None
    assert result.config == AppConfig()


def test_invalid_gesture_threshold_order_is_rejected() -> None:
    with pytest.raises(ValidationError, match="closed threshold"):
        GestureSettings(wink_closed_threshold=0.8, wink_open_threshold=0.4)


def test_invalid_temple_threshold_order_is_rejected() -> None:
    with pytest.raises(ValidationError, match="temple enter ratio"):
        GestureSettings(temple_enter_ratio=0.1, temple_exit_ratio=0.1)


def test_temple_semantic_timing_defaults_and_bounds() -> None:
    settings = GestureSettings()

    assert settings.temple_hold_threshold_ms == 550
    assert settings.temple_cooldown_ms == 250
    with pytest.raises(ValidationError, match="temple_hold_threshold_ms"):
        GestureSettings(temple_hold_threshold_ms=49)
    with pytest.raises(ValidationError, match="temple_cooldown_ms"):
        GestureSettings(temple_cooldown_ms=-1)


def test_active_profile_name_uses_repository_safe_validation() -> None:
    assert AppSettings(active_profile=" Work ").active_profile == "Work"

    with pytest.raises(ValidationError, match="profile name"):
        AppSettings(active_profile="../escape")


def test_emergency_shortcut_migrates_reserved_f12_and_rejects_other_values() -> None:
    migrated = TrackingSettings.model_validate({"emergency_shortcut": "CTRL+ALT+F12"})

    assert migrated.emergency_shortcut == "CTRL+ALT+SHIFT+F11"
    with pytest.raises(ValidationError, match="emergency_shortcut"):
        TrackingSettings.model_validate({"emergency_shortcut": "CTRL+ALT+DELETE"})
