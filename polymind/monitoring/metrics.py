"""
Operational metrics collector for the Polymind daemon.

Tracks orders, fills, cancellations, errors, P&L, and latency
across the trading engine lifecycle. Provides point-in-time
:class:`MetricsSnapshot` objects for reporting and dashboards.

Usage::

    collector = MetricsCollector()
    collector.record_order_placed()
    collector.record_fill()
    collector.record_error()
    snap = collector.snapshot()
    print(snap.fill_rate, snap.total_pnl)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MetricsSnapshot:
    """Point-in-time snapshot of operational metrics.

    Attributes:
        timestamp: When this snapshot was taken.
        orders_placed: Total orders placed since start/reset.
        orders_filled: Total orders filled.
        orders_cancelled: Total orders cancelled.
        errors: Total errors encountered.
        total_pnl: Cumulative realised P&L.
        avg_latency_ms: Average order latency in milliseconds.
        min_latency_ms: Minimum observed latency.
        max_latency_ms: Maximum observed latency.
        up_time_seconds: Seconds since collector creation or reset.
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    orders_placed: int = 0
    orders_filled: int = 0
    orders_cancelled: int = 0
    errors: int = 0
    total_pnl: float = 0.0
    avg_latency_ms: float | None = None
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    up_time_seconds: float = 0.0

    @property
    def fill_rate(self) -> float:
        """Fraction of placed orders that were filled (0.0–1.0)."""
        if self.orders_placed == 0:
            return 0.0
        return self.orders_filled / self.orders_placed

    @property
    def error_rate(self) -> float:
        """Fraction of placed orders that resulted in errors (0.0–1.0)."""
        if self.orders_placed == 0:
            return 0.0
        return self.errors / self.orders_placed

    @property
    def cancellation_rate(self) -> float:
        """Fraction of placed orders that were cancelled (0.0–1.0)."""
        if self.orders_placed == 0:
            return 0.0
        return self.orders_cancelled / self.orders_placed

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON/logging output."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "orders_placed": self.orders_placed,
            "orders_filled": self.orders_filled,
            "orders_cancelled": self.orders_cancelled,
            "errors": self.errors,
            "total_pnl": self.total_pnl,
            "fill_rate": self.fill_rate,
            "error_rate": self.error_rate,
            "cancellation_rate": self.cancellation_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "min_latency_ms": self.min_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "up_time_seconds": self.up_time_seconds,
        }


class MetricsCollector:
    """Collects operational metrics for the trading engine.

    Thread-safe counters that accumulate over time. Call :meth:`snapshot`
    at any point to get a point-in-time view, or :meth:`reset` to clear.
    """

    def __init__(self) -> None:
        self._start_time = time.time()
        self._orders_placed = 0
        self._orders_filled = 0
        self._orders_cancelled = 0
        self._errors = 0
        self._total_pnl = 0.0
        self._latencies: list[float] = []

    # ── Record methods ───────────────────────────────────────────────

    def record_order_placed(self, count: int = 1) -> None:
        """Record that *count* orders were placed."""
        self._orders_placed += count

    def record_fill(self, count: int = 1) -> None:
        """Record that *count* orders were filled."""
        self._orders_filled += count

    def record_cancellation(self, count: int = 1) -> None:
        """Record that *count* orders were cancelled."""
        self._orders_cancelled += count

    def record_error(self, count: int = 1) -> None:
        """Record that *count* errors occurred."""
        self._errors += count

    def record_pnl(self, pnl: float) -> None:
        """Record a realised P&L amount (positive = profit)."""
        self._total_pnl += pnl

    def record_latency(self, latency_ms: float) -> None:
        """Record an order latency measurement in milliseconds."""
        self._latencies.append(latency_ms)

    # ── Snapshot ─────────────────────────────────────────────────────

    def snapshot(self) -> MetricsSnapshot:
        """Return a point-in-time snapshot of all metrics."""
        avg_lat = None
        min_lat = None
        max_lat = None
        if self._latencies:
            avg_lat = sum(self._latencies) / len(self._latencies)
            min_lat = min(self._latencies)
            max_lat = max(self._latencies)

        return MetricsSnapshot(
            timestamp=datetime.now(timezone.utc),
            orders_placed=self._orders_placed,
            orders_filled=self._orders_filled,
            orders_cancelled=self._orders_cancelled,
            errors=self._errors,
            total_pnl=self._total_pnl,
            avg_latency_ms=avg_lat,
            min_latency_ms=min_lat,
            max_latency_ms=max_lat,
            up_time_seconds=time.time() - self._start_time,
        )

    def reset(self) -> None:
        """Reset all counters to zero."""
        self._start_time = time.time()
        self._orders_placed = 0
        self._orders_filled = 0
        self._orders_cancelled = 0
        self._errors = 0
        self._total_pnl = 0.0
        self._latencies.clear()

    def merge(self, other: MetricsCollector) -> MetricsSnapshot:
        """Merge this collector with another and return a combined snapshot.

        Both collectors are left unchanged.
        """
        both = self.snapshot()
        other_snap = other.snapshot()
        return MetricsSnapshot(
            timestamp=datetime.now(timezone.utc),
            orders_placed=both.orders_placed + other_snap.orders_placed,
            orders_filled=both.orders_filled + other_snap.orders_filled,
            orders_cancelled=both.orders_cancelled + other_snap.orders_cancelled,
            errors=both.errors + other_snap.errors,
            total_pnl=both.total_pnl + other_snap.total_pnl,
            up_time_seconds=max(both.up_time_seconds, other_snap.up_time_seconds),
        )

    def __str__(self) -> str:
        snap = self.snapshot()
        return (
            f"MetricsCollector("
            f"orders_placed={snap.orders_placed}, "
            f"orders_filled={snap.orders_filled}, "
            f"orders_cancelled={snap.orders_cancelled}, "
            f"errors={snap.errors}, "
            f"pnl={snap.total_pnl:.2f})"
        )
