"""Structured JSON logging for Grimoire."""

from __future__ import annotations

import json
import logging
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """Format log records as JSON objects, one per line."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        from datetime import datetime, timezone

        log_entry: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.name,
            "attributes": getattr(record, "attributes", {}),
        }

        # Add trace context if available
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx.is_valid:
                log_entry["trace_id"] = format(ctx.trace_id, "032x")
                log_entry["span_id"] = format(ctx.span_id, "016x")
        except Exception:  # noqa: BLE001
            pass

        return json.dumps(log_entry)


def setup_logging(log_file: Path | None = None, level: str = "INFO") -> None:
    """Configure structured JSON logging to both stdout and file."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = JsonFormatter()

    # Stdout handler
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    # File handler (if configured)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file))
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
