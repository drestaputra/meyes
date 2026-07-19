"""Structured rotating application logging."""

from __future__ import annotations

import json
import logging
from collections.abc import MutableMapping
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from typing import Any

from meyes.util.paths import AppPaths

_RESERVED = frozenset(logging.makeLogRecord({}).__dict__)


class JsonLogFormatter(logging.Formatter):
    """Format conservative JSON-lines logs for local diagnostics."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "category": getattr(record, "category", "APP"),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in {"category", "message"}:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class CategoryLoggerAdapter(logging.LoggerAdapter[logging.Logger]):
    """Bind a category while preserving per-call structured fields."""

    def process(
        self, msg: object, kwargs: MutableMapping[str, Any]
    ) -> tuple[object, MutableMapping[str, Any]]:
        merged_extra: dict[str, object] = dict(self.extra or {})
        call_extra = kwargs.get("extra")
        if isinstance(call_extra, dict):
            merged_extra.update(call_extra)
        kwargs["extra"] = merged_extra
        return msg, kwargs


def setup_logging(paths: AppPaths, level: str = "INFO") -> None:
    """Configure one rotating local log handler."""
    paths.ensure_directories()
    root = logging.getLogger("meyes")
    root.setLevel(level)
    root.propagate = False
    root.handlers.clear()

    handler = RotatingFileHandler(
        paths.log_file,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)


def get_logger(category: str) -> CategoryLoggerAdapter:
    """Return a category-bound logger adapter."""
    return CategoryLoggerAdapter(logging.getLogger("meyes"), {"category": category})
