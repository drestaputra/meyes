"""Windows-appropriate local application paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Resolved per-user paths used by MEYES."""

    config_dir: Path
    data_dir: Path
    log_dir: Path

    @classmethod
    def for_user(cls) -> AppPaths:
        """Resolve production paths for the current Windows user."""
        roaming_dirs = PlatformDirs(appname="Meyes", appauthor=False, roaming=True)
        local_dirs = PlatformDirs(appname="Meyes", appauthor=False, roaming=False)
        return cls(
            config_dir=Path(roaming_dirs.user_config_path),
            data_dir=Path(local_dirs.user_data_path),
            log_dir=Path(local_dirs.user_log_path),
        )

    @classmethod
    def under(cls, root: Path) -> AppPaths:
        """Create isolated paths for tests."""
        return cls(
            config_dir=root / "config",
            data_dir=root / "data",
            log_dir=root / "logs",
        )

    @property
    def config_file(self) -> Path:
        """Canonical JSON configuration path."""
        return self.config_dir / "config.json"

    @property
    def log_file(self) -> Path:
        """Canonical rotating log path."""
        return self.log_dir / "meyes.log"

    def ensure_directories(self) -> None:
        """Create private application directories when missing."""
        for directory in (self.config_dir, self.data_dir, self.log_dir):
            directory.mkdir(parents=True, exist_ok=True)
