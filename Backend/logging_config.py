"""Minimal structured (JSON) logging — stdlib only, no dependency."""
import json
import logging
import sys
from datetime import datetime, timezone

_EXTRA_KEYS = (
    "event", "session_id", "message_len", "rewritten",
    "top_score", "n_chunks", "found_in_kb", "latency_ms", "query",
)


class JsonFormatter(logging.Formatter):
    """Render each record as a single-line JSON object, lifting known `extra`
    fields to top level."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in _EXTRA_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # ensure_ascii=True: the line is pure ASCII, so it can never raise
        # UnicodeEncodeError on a non-UTF-8 stdout (Windows cp1252, odd locales).
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(level: str = "INFO") -> None:
    """Install one JSON StreamHandler on the root logger. Idempotent, and it
    does NOT clear existing handlers (so pytest's caplog handler survives)."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in root.handlers:
        if isinstance(handler.formatter, JsonFormatter):
            return  # already configured
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
