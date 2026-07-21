"""Validated application configuration models."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from meyes.calibration.acceptance import CalibrationAcceptancePolicy
from meyes.cursor.gate import CursorGateSettings
from meyes.cursor.smoothing import OneEuroFilterSettings
from meyes.util.profile_names import validate_profile_name


class StrictConfigModel(BaseModel):
    """Base class that rejects unknown configuration keys."""

    model_config = ConfigDict(extra="forbid")


class AppSettings(StrictConfigModel):
    """General application settings."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    first_run: bool = True
    active_profile: str = Field(default="Default", min_length=1, max_length=80)

    @field_validator("active_profile", mode="before")
    @classmethod
    def validate_active_profile(cls, value: object) -> object:
        return validate_profile_name(value)


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
    emergency_shortcut: Literal["CTRL+ALT+SHIFT+F11"] = "CTRL+ALT+SHIFT+F11"

    @field_validator("emergency_shortcut", mode="before")
    @classmethod
    def migrate_reserved_emergency_shortcut(cls, value: object) -> object:
        if value == "CTRL+ALT+F12":
            return "CTRL+ALT+SHIFT+F11"
        return value


class GestureSettings(StrictConfigModel):
    """Gesture thresholds and timing in milliseconds."""

    wink_closed_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    wink_open_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    wink_min_duration_ms: int = Field(default=140, ge=50, le=2000)
    wink_max_duration_ms: int = Field(default=900, ge=100, le=5000)
    wink_cooldown_ms: int = Field(default=350, ge=0, le=5000)
    both_eye_sync_window_ms: int = Field(default=90, ge=0, le=1000)
    temple_enter_ratio: float = Field(default=0.075, ge=0.0, le=1.0)
    temple_exit_ratio: float = Field(default=0.095, ge=0.0, le=1.0)
    temple_stabilization_ms: int = Field(default=180, ge=0, le=5000)
    temple_hold_threshold_ms: int = Field(default=550, ge=50, le=5000)
    temple_cooldown_ms: int = Field(default=250, ge=0, le=5000)
    tracking_timeout_ms: int = Field(default=250, ge=50, le=5000)

    @model_validator(mode="after")
    def validate_threshold_order(self) -> Self:
        if self.wink_closed_threshold >= self.wink_open_threshold:
            raise ValueError("wink closed threshold must be lower than open threshold")
        if self.wink_min_duration_ms >= self.wink_max_duration_ms:
            raise ValueError("wink minimum duration must be lower than maximum duration")
        if self.temple_enter_ratio >= self.temple_exit_ratio:
            raise ValueError("temple enter ratio must be lower than exit ratio")
        return self


class UiSettings(StrictConfigModel):
    """Persistent user-interface preferences."""

    selected_page: Literal[
        "Dashboard",
        "Calibration",
        "Bindings",
        "Live Input",
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


class CalibrationSettings(StrictConfigModel):
    """Optional evidence limits; all remain unset until representative measurement."""

    maximum_root_mean_square_error: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        strict=True,
    )
    maximum_mean_error: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        strict=True,
    )
    maximum_error: float | None = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        strict=True,
    )
    minimum_holdout_samples: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode="after")
    def validate_complete_policy(self) -> Self:
        values = (
            self.maximum_root_mean_square_error,
            self.maximum_mean_error,
            self.maximum_error,
            self.minimum_holdout_samples,
        )
        if any(value is not None for value in values) and not all(
            value is not None for value in values
        ):
            raise ValueError("calibration acceptance limits must be all configured or all unset")
        return self

    @property
    def acceptance_policy(self) -> CalibrationAcceptancePolicy | None:
        values = (
            self.maximum_root_mean_square_error,
            self.maximum_mean_error,
            self.maximum_error,
            self.minimum_holdout_samples,
        )
        if any(value is None for value in values):
            return None
        maximum_rmse, maximum_mean, maximum_error, minimum_samples = values
        assert isinstance(maximum_rmse, float)
        assert isinstance(maximum_mean, float)
        assert isinstance(maximum_error, float)
        assert isinstance(minimum_samples, int)
        return CalibrationAcceptancePolicy(
            maximum_root_mean_square_error=maximum_rmse,
            maximum_mean_error=maximum_mean,
            maximum_error=maximum_error,
            minimum_holdout_samples=minimum_samples,
        )


class CursorSettings(StrictConfigModel):
    """Smoothing and movement-gate values shared by diagnostics and Live Input."""

    minimum_cutoff: float = Field(
        default=1.0,
        gt=0,
        allow_inf_nan=False,
        strict=True,
    )
    speed_coefficient: float = Field(
        default=0.01,
        ge=0,
        allow_inf_nan=False,
        strict=True,
    )
    derivative_cutoff: float = Field(
        default=1.0,
        gt=0,
        allow_inf_nan=False,
        strict=True,
    )
    maximum_gap_ms: int = Field(default=250, ge=50, le=5000, strict=True)
    freeze_during_temple_gesture: bool = True
    resume_delay_ms: int = Field(default=120, ge=0, le=5000, strict=True)

    @property
    def filter_settings(self) -> OneEuroFilterSettings:
        return OneEuroFilterSettings(
            minimum_cutoff=self.minimum_cutoff,
            speed_coefficient=self.speed_coefficient,
            derivative_cutoff=self.derivative_cutoff,
            maximum_gap_seconds=self.maximum_gap_ms / 1000.0,
        )

    @property
    def gate_settings(self) -> CursorGateSettings:
        return CursorGateSettings(
            freeze_during_temple_gesture=self.freeze_during_temple_gesture,
            resume_delay_seconds=self.resume_delay_ms / 1000.0,
        )


class AppConfig(StrictConfigModel):
    """Root versioned configuration document."""

    schema_version: Literal[1] = 1
    app: AppSettings = Field(default_factory=AppSettings)
    camera: CameraSettings = Field(default_factory=CameraSettings)
    tracking: TrackingSettings = Field(default_factory=TrackingSettings)
    gestures: GestureSettings = Field(default_factory=GestureSettings)
    calibration: CalibrationSettings = Field(default_factory=CalibrationSettings)
    cursor: CursorSettings = Field(default_factory=CursorSettings)
    ui: UiSettings = Field(default_factory=UiSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
