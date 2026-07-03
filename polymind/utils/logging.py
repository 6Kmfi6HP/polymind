"""
Logging utilities for Polymind.

Provides structured logging setup with consistent formatting.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


@dataclass
class LogConfig:
    """Configuration for a logger instance."""

    name: str
    level: str = "INFO"
    format_str: str | None = None
    log_file: str | None = None
    json_output: bool = False


class _JsonFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "funcName": record.funcName,
                "line": record.lineno,
            }
        )


def setup_logging(config: LogConfig) -> logging.Logger:
    """Configure and return a logger based on *config*.

    Args:
        config: A :class:`LogConfig` instance describing the logger to set up.

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(config.name)

    if logger.handlers:
        return logger

    fmt = config.format_str if config.format_str is not None else DEFAULT_FORMAT

    logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))
    logger.propagate = False

    if config.log_file is not None:
        log_path = Path(config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(str(log_path))
    else:
        handler = logging.StreamHandler(sys.stdout)

    if config.json_output:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(fmt))

    logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get an existing logger or create a default one.

    If *name* already has a configured logger it is returned as-is.
    Otherwise a new logger is created with :func:`setup_logging` using
    default settings (INFO level, stdout, text format).

    Args:
        name: Logger name.

    Returns:
        A :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    return setup_logging(LogConfig(name=name, level="INFO"))
