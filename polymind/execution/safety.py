"""
Preflight validation, kill switch, and log redaction for execution safety.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from polymind.core.intents import StrategyIntent


# ── PreflightChecker ──────────────────────────────────────────────────────


@dataclass
class PreflightResult:
    """Result of a preflight check."""

    valid: bool
    errors: List[str]


class PreflightChecker:
    """Validate a StrategyIntent before execution.

    Checks for common errors: negative prices, negative sizes, excessive
    order counts, missing market IDs, and other easily-detectable issues
    that should never reach an executor.
    """

    def __init__(self, max_orders_per_intent: int = 20):
        self.max_orders_per_intent = max_orders_per_intent

    async def check(self, intent: StrategyIntent) -> PreflightResult:
        """Run all validation checks and return a result."""
        errors: List[str] = []

        # Check for too many orders
        if len(intent.orders) > self.max_orders_per_intent:
            errors.append(
                f"Order count {len(intent.orders)} exceeds "
                f"max {self.max_orders_per_intent}"
            )

        # Validate each order
        for i, order in enumerate(intent.orders):
            if not order.market_id:
                errors.append(f"Order {i}: market_id is empty")
            if order.price < 0:
                errors.append(f"Order {i}: negative price {order.price}")
            if order.size < 0:
                errors.append(f"Order {i}: negative size {order.size}")

        return PreflightResult(valid=len(errors) == 0, errors=errors)


# ── KillSwitch ────────────────────────────────────────────────────────────


class KillSwitch:
    """Emergency stop that halts new order placement.

    When engaged, the executor should check is_active before executing
    any StrategyIntent and refuse if engaged.
    """

    def __init__(self) -> None:
        self._active: bool = False
        self._reason: str = ""
        self._engaged_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        """Whether the kill switch is currently engaged."""
        return self._active

    @property
    def reason(self) -> str:
        """Reason the kill switch was engaged."""
        return self._reason

    @property
    def engaged_at(self) -> Optional[datetime]:
        """Timestamp when the kill switch was engaged."""
        return self._engaged_at

    def engage(self, reason: str) -> None:
        """Engage the kill switch with a given reason."""
        self._active = True
        self._reason = reason
        self._engaged_at = datetime.now(timezone.utc)

    def release(self) -> None:
        """Release the kill switch."""
        self._active = False
        self._reason = ""
        self._engaged_at = None


# ── LogRedaction ──────────────────────────────────────────────────────────


class LogRedaction:
    """Redact sensitive data from log messages.

    Patterns are compiled on init and applied via ``redact()``.
    Add custom patterns by passing a list of regex strings.
    """

    # Default patterns for common sensitive data
    DEFAULT_PATTERNS = [
        re.compile(r"(?i)(api[_-]?key|apikey|secret|password|token)\s*[=:]\s*\S+"),
        re.compile(r"0x[a-fA-F0-9]{16,}"),  # Ethereum-style addresses / keys
        re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),  # sk-xxx API keys
        re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"),  # JWT
    ]

    def __init__(self, custom_patterns: Optional[List[str]] = None):
        self._patterns = list(self.DEFAULT_PATTERNS)
        if custom_patterns:
            for pat in custom_patterns:
                self._patterns.append(re.compile(pat))

    def redact(self, message: str) -> str:
        """Return the message with sensitive data replaced by ``***``."""
        for pattern in self._patterns:
            message = pattern.sub("***", message)
        return message
