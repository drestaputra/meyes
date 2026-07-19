"""Validated application configuration models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictConfigModel(BaseModel):
    """Base class that rejects unknown configuration keys."""

    model_config = ConfigDict(extra="forbid")


class AppSettings(StrictConfigModel):
    """General application settings."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    first_run: bool = True
    active_profile: str = Field(default="Default", min_length=1, max_length=80)


class CameraSettings(StrictConfigModel):
    """Camera capture defaults."""

    camera_index: int = Field(default=0, ge=0, le=32)
    width: int = Field(default=640, ge=320, le=3840)
    height: int = Field(default=480, ge=240, le=2160)
    target_fps: int = Field(default=30, ge=1, le=120)
    mirror: bool = True


class TrackingSettings(StrictConfigModel):
    """Global tracking safety settings."""

    enabled_on_startup: bool = False
    safe_mode: bool = True
    emergency_shortcut: str = "CTRL+ALT+F12"


class UiSettings(StrictConfigModel):
    """Persistent user-interface preferences."""

    selected_page: Literal[
        "Dashboard",
        "Calibration",
        "Bindings",
        "Sensitivity",
        "Camera",
        "Profiles",
        "Diagnostics",
        "Privacy",
    ] = "Dashboard"
    window_width: int = Field(default=1200, ge=900, le=3840)
    window_height: int = Field(default=760, ge=640, le=2160)


class PrivacySettings(StrictConfigModel):
    """Privacy controls; recording remains opt-in."""

    diagnostic_recording_enabled: bool = False


class AppConfig(StrictConfigModel):
    """Root versioned configuration document."""

    schema_version: Literal[1] = 1
    app: AppSettings = Field(default_factory=AppSettings)
    camera: CameraSettings = Field(default_factory=CameraSettings)
    tracking: TrackingSettings = Field(default_factory=TrackingSettings)
    ui: UiSettings = Field(default_factory=UiSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
