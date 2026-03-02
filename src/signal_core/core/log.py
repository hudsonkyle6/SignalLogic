"""
Centralized logging for SignalLogic.

Configure once at process startup via configure().  All other modules call
get_logger(__name__) to get a module-scoped Logger.

Environment variables:
    LOG_LEVEL   — DEBUG | INFO | WARNING | ERROR   (default: INFO)
    LOG_FORMAT  — json | text                       (default: text)

In production containers set LOG_FORMAT=json to get newline-delimited JSON
that log shippers (Fluentd, Logstash, CloudWatch, Datadog) can parse
directly.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    """Single-line JSON log records for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, separators=(",", ":"), ensure_ascii=False)


_TEXT_FMT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%SZ"

_configured = False


def configure() -> None:
    """
    Wire up the root logger.  Call once at process entry (main()).
    Safe to call multiple times — only the first call has effect.
    """
    global _configured
    if _configured:
        return
    _configured = True

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = os.environ.get("LOG_FORMAT", "text").lower()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_TEXT_FMT, datefmt=_DATE_FMT))

    root = logging.getLogger()
    root.setLevel(level)
    # Remove any handlers added before configure() was called (e.g. by basicConfig)
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger.  Call at module level: log = get_logger(__name__)"""
    return logging.getLogger(name)
