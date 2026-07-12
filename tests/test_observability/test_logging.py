"""Tests for structured JSON logging."""

from __future__ import annotations

import json
import logging
from pathlib import Path


def test_json_formatter_produces_valid_json() -> None:
    """JsonFormatter.format returns a valid JSON string."""
    from grimoire.observability.logging import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.module",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello world"
    assert parsed["module"] == "test.module"
    assert "timestamp" in parsed


def test_json_formatter_includes_attributes() -> None:
    """JsonFormatter includes custom attributes from the log record."""
    from grimoire.observability.logging import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="test.py",
        lineno=1,
        msg="with attrs",
        args=(),
        exc_info=None,
    )
    record.attributes = {"repo": "org/alpha"}  # type: ignore[attr-defined]

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["attributes"] == {"repo": "org/alpha"}


def test_setup_logging_creates_file_handler(tmp_path: Path) -> None:
    """setup_logging creates a file handler when log_file is provided."""
    from grimoire.observability.logging import JsonFormatter, setup_logging

    log_file = tmp_path / "logs" / "test.log"

    # Use a named logger to avoid polluting the root logger for other tests
    test_logger = logging.getLogger("test_setup_logging")
    test_logger.handlers.clear()

    # Temporarily monkey-patch getLogger to return our test logger
    original_get_logger = logging.getLogger
    logging.getLogger = lambda name=None: (
        test_logger if name is None or name == "" else original_get_logger(name)
    )  # type: ignore[assignment,misc]

    try:
        setup_logging(log_file=log_file, level="DEBUG")
    finally:
        logging.getLogger = original_get_logger  # type: ignore[assignment]

    assert log_file.parent.exists()

    # Check that at least one handler uses JsonFormatter
    has_json_handler = any(
        isinstance(h.formatter, JsonFormatter) for h in test_logger.handlers
    )
    assert has_json_handler

    # Clean up handlers
    test_logger.handlers.clear()
