"""
Telegram alerting for strategy events, errors, and performance reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Alert:
    """A single alert event."""

    level: str  # INFO, WARN, ERROR, CRITICAL
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""


class AlertManager:
    """Manages alert delivery across channels.

    Currently logs to console. Production: send to Telegram/webhook.
    """

    def __init__(self):
        self._alerts: List[Alert] = []

    def info(self, message: str, source: str = "") -> None:
        self._alerts.append(Alert("INFO", message, source=source))

    def warn(self, message: str, source: str = "") -> None:
        self._alerts.append(Alert("WARN", message, source=source))

    def error(self, message: str, source: str = "") -> None:
        self._alerts.append(Alert("ERROR", message, source=source))

    def critical(self, message: str, source: str = "") -> None:
        self._alerts.append(Alert("CRITICAL", message, source=source))

    def get_recent(self, n: int = 10) -> List[Alert]:
        return self._alerts[-n:]

    def get_unread_count(self) -> int:
        return len(self._alerts)

    def clear(self) -> None:
        self._alerts.clear()
