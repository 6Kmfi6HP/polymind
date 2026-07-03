"""
Tests for polymind.utils.logging.
"""

from __future__ import annotations

import json
import logging

from polymind.utils.logging import LogConfig, get_logger, setup_logging


class TestLogConfig:
    def test_defaults(self):
        cfg = LogConfig(name="test")
        assert cfg.name == "test"
        assert cfg.level == "INFO"
        assert cfg.format_str is None
        assert cfg.log_file is None
        assert cfg.json_output is False

    def test_custom_values(self):
        cfg = LogConfig(
            name="custom",
            level="DEBUG",
            format_str="%(message)s",
            log_file="/tmp/test.log",
            json_output=True,
        )
        assert cfg.name == "custom"
        assert cfg.level == "DEBUG"
        assert cfg.format_str == "%(message)s"
        assert cfg.log_file == "/tmp/test.log"
        assert cfg.json_output is True


class TestSetupLogging:
    def test_returns_logger_with_correct_name(self):
        logger = setup_logging(LogConfig(name="test_logger"))
        assert logger.name == "test_logger"
        assert isinstance(logger, logging.Logger)

    def test_default_level_is_info(self):
        logger = setup_logging(LogConfig(name="test_default_level"))
        assert logger.level == logging.INFO

    def test_custom_level(self):
        logger = setup_logging(LogConfig(name="test_debug", level="DEBUG"))
        assert logger.level == logging.DEBUG

    def test_does_not_duplicate_handlers(self):
        logger = setup_logging(LogConfig(name="test_no_dup"))
        count = len(logger.handlers)
        setup_logging(LogConfig(name="test_no_dup"))
        assert len(logger.handlers) == count

    def test_json_output_formats_as_json(self):
        logger = setup_logging(LogConfig(name="test_json", json_output=True))
        # Capture output via a handler we can inspect
        from io import StringIO

        stream = StringIO()
        # Replace handler with one writing to our stream
        logger.handlers.clear()
        handler = logging.StreamHandler(stream)
        from polymind.utils.logging import _JsonFormatter

        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        logger.info("hello json")
        output = stream.getvalue().strip()
        record = json.loads(output)
        assert record["level"] == "INFO"
        assert record["message"] == "hello json"
        assert record["name"] == "test_json"

    def test_text_format_with_custom_format_str(self):
        logger = setup_logging(LogConfig(name="test_fmt", format_str="%(levelname)s:%(message)s"))
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.formatter._fmt == "%(levelname)s:%(message)s"

    def test_log_file_creates_file(self):
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            log_path = f.name

        try:
            logger = setup_logging(LogConfig(name="test_file", log_file=log_path))
            logger.info("file log message")
            # Flush and check
            for handler in logger.handlers:
                handler.flush()

            with open(log_path) as f:
                content = f.read()
            assert "file log message" in content
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)


class TestGetLogger:
    def test_creates_new_logger(self):
        logger = get_logger("fresh_logger")
        assert logger.name == "fresh_logger"
        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.INFO

    def test_returns_same_instance_for_same_name(self):
        a = get_logger("shared_logger")
        b = get_logger("shared_logger")
        assert a is b

    def test_returns_existing_logger_with_handlers(self):
        """If a logger already has handlers, get_logger returns it as-is."""
        existing = logging.getLogger("preconfigured")
        existing.setLevel(logging.DEBUG)
        existing.addHandler(logging.StreamHandler())

        result = get_logger("preconfigured")
        assert result is existing
        assert result.level == logging.DEBUG
