"""
Adapter instrumentation — Prometheus counters and histograms.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Counter:
    """Simple monotonic counter (Prometheus Counter equivalent)."""

    name: str
    _value: int = 0

    def inc(self, amount: int = 1) -> None:
        self._value += amount

    @property
    def value(self) -> int:
        return self._value


@dataclass
class Histogram:
    """Simple histogram for latency distributions."""

    name: str
    _buckets: tuple = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    _counts: Dict[float, int] = field(default_factory=lambda: {})
    _sum: float = 0.0
    _total_count: int = 0

    def __post_init__(self):
        for b in self._buckets:
            self._counts[b] = 0

    def observe(self, value: float) -> None:
        """Record an observation (typically a duration in seconds)."""
        self._sum += value
        self._total_count += 1
        for bucket in self._buckets:
            if value <= bucket:
                self._counts[bucket] += 1

    @property
    def count(self) -> int:
        return self._total_count

    @property
    def sum(self) -> float:
        return self._sum


class AdapterMetrics:
    """Collector for adapter-level metrics.

    Each adapter module creates its own instance with a unique prefix.
    """

    def __init__(self, prefix: str):
        self.prefix = prefix
        self.calls_total: Counter = Counter(f"{prefix}_calls_total")
        self.errors_total: Counter = Counter(f"{prefix}_errors_total")
        self.retries_total: Counter = Counter(f"{prefix}_retries_total")
        self.latency_seconds: Histogram = Histogram(f"{prefix}_latency_seconds")
        self.ws_disconnects_total: Counter = Counter(f"{prefix}_ws_disconnects_total")
        self.ws_reconnects_total: Counter = Counter(f"{prefix}_ws_reconnects_total")
        self.ws_messages_received: Counter = Counter(f"{prefix}_ws_messages_received")

    @contextmanager
    def measure(self):
        """Context manager that records call duration.
        Increments errors_total if the body raises.
        """
        import time
        start = time.monotonic()
        try:
            yield
        except Exception:
            self.errors_total.inc()
            raise
        finally:
            self.latency_seconds.observe(time.monotonic() - start)
            self.calls_total.inc()
