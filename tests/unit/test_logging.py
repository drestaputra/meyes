"""Structured local logging tests."""

from __future__ import annotations

import json
from pathlib import Path

from meyes.util.logging import get_logger, setup_logging
from meyes.util.paths import AppPaths


def test_structured_log_contains_category_and_fields(tmp_path: Path) -> None:
    paths = AppPaths.under(tmp_path)
    setup_logging(paths, "INFO")

    get_logger("CONFIG").info("config_loaded", extra={"schema_version": 1})

    record = json.loads(paths.log_file.read_text(encoding="utf-8"))
    assert record["level"] == "INFO"
    assert record["category"] == "CONFIG"
    assert record["message"] == "config_loaded"
    assert record["schema_version"] == 1
