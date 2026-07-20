"""Atomic local JSON configuration persistence."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from meyes.config.models import AppConfig
from meyes.util.paths import AppPaths

Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class ConfigLoadResult:
    """Configuration plus any recovery information for the UI/log."""

    config: AppConfig
    warning: str | None = None
    recovered_from: Path | None = None


class ConfigManager:
    """Load and save the versioned application configuration."""

    def __init__(self, paths: AppPaths, clock: Clock | None = None) -> None:
        self._paths = paths
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def config_path(self) -> Path:
        """Return the canonical config path."""
        return self._paths.config_file

    @property
    def paths(self) -> AppPaths:
        """Return the immutable application path set used by related repositories."""
        return self._paths

    def load(self) -> ConfigLoadResult:
        """Load config, recovering safely from malformed or invalid data."""
        self._paths.ensure_directories()
        if not self.config_path.exists():
            config = AppConfig()
            self.save(config)
            return ConfigLoadResult(config=config)

        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
            return ConfigLoadResult(config=AppConfig.model_validate(payload))
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as error:
            backup_path = self._backup_invalid_config()
            config = AppConfig()
            self.save(config)
            return ConfigLoadResult(
                config=config,
                warning=f"Invalid configuration was replaced with safe defaults: {error}",
                recovered_from=backup_path,
            )

    def save(self, config: AppConfig) -> None:
        """Persist config atomically as human-readable UTF-8 JSON."""
        self._paths.ensure_directories()
        temporary_path = self.config_path.with_suffix(".json.tmp")
        serialized = config.model_dump_json(indent=2)
        temporary_path.write_text(f"{serialized}\n", encoding="utf-8")
        temporary_path.replace(self.config_path)

    def _backup_invalid_config(self) -> Path | None:
        if not self.config_path.exists():
            return None
        stamp = self._clock().astimezone(UTC).strftime("%Y%m%d-%H%M%S-%f")
        backup_path = self.config_path.with_name(f"config.invalid-{stamp}.json")
        self.config_path.replace(backup_path)
        return backup_path
