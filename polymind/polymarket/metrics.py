"""
Adapter instrumentation — request/error tracking, latency percentiles, summary reports.
"""

from __future__ import annotations

import math
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field


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
    _counts: dict[float, int] = field(default_factory=lambda: {})
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


@dataclass
class MetricsSummary:
    """Aggregate metrics snapshot for one adapter or endpoint."""

    total_requests: int = 0
    total_errors: int = 0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    per_endpoint: dict = field(default_factory=dict)


class AdapterMetrics:
    """Collector for adapter-level metrics.

    Each adapter module creates its own instance with a unique prefix.

    Tracks per-endpoint request counts, error counts, and latency samples
    for computing percentiles and summary reports.
    """

    def __init__(self, prefix: str):
        self.prefix = prefix
        self._lock = threading.Lock()

        # Aggregate counters (Prometheus-style)
        self.calls_total: Counter = Counter(f"{prefix}_calls_total")
        self.errors_total: Counter = Counter(f"{prefix}_errors_total")
        self.retries_total: Counter = Counter(f"{prefix}_retries_total")
        self.latency_seconds: Histogram = Histogram(f"{prefix}_latency_seconds")
        self.ws_disconnects_total: Counter = Counter(f"{prefix}_ws_disconnects_total")
        self.ws_reconnects_total: Counter = Counter(f"{prefix}_ws_reconnects_total")
        self.ws_messages_received: Counter = Counter(f"{prefix}_ws_messages_received")

        # Per-endpoint detailed tracking
        self._request_counts: dict[str, int] = {}
        self._error_counts: dict[str, int] = {}
        self._latencies: dict[str, list[float]] = {}

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def record_request(self, method: str, endpoint: str, duration_ms: float, status_code: int) -> None:
        """Record a single API request.

        Updates aggregate counters and per-endpoint stats.  *duration_ms*
        is stored in milliseconds for percentile computation; the histogram
        always stores in seconds.
        """
        with self._lock:
            self.calls_total.inc()
            self._request_counts[endpoint] = self._request_counts.get(endpoint, 0) + 1
            # Store raw ms for percentile calculations
            self._latencies.setdefault(endpoint, []).append(duration_ms)
            # Aggregate histogram uses seconds
            self.latency_seconds.observe(duration_ms / 1000.0)

    def record_error(self, method: str, endpoint: str, error_type: str) -> None:
        """Record an error for *endpoint*."""
        with self._lock:
            self.errors_total.inc()
            self._error_counts[endpoint] = self._error_counts.get(endpoint, 0) + 1

    def get_request_count(self, endpoint: str | None = None) -> int:
        """Return total request count, optionally filtered by *endpoint*."""
        with self._lock:
            if endpoint is not None:
                return self._request_counts.get(endpoint, 0)
            return self.calls_total.value

    def get_error_rate(self, endpoint: str | None = None) -> float:
        """Return error rate (0.0 – 1.0), optionally filtered by *endpoint*."""
        with self._lock:
            if endpoint is not None:
                total = self._request_counts.get(endpoint, 0)
                errors = self._error_counts.get(endpoint, 0)
            else:
                total = self.calls_total.value
                errors = self.errors_total.value
            if total == 0:
                return 0.0
            return errors / total

    def get_latency_percentile(self, endpoint: str | None = None, percentile: float = 50.0) -> float:
        """Return the latency value at *percentile* (0–100) in milliseconds.

        When *endpoint* is ``None`` all recorded latencies are pooled.
        """
        with self._lock:
            if endpoint is not None:
                samples = self._latencies.get(endpoint, [])
            else:
                # Pool all endpoints
                samples = [
                    ms
                    for ep_samples in self._latencies.values()
                    for ms in ep_samples
                ]
            if not samples:
                return 0.0
            sorted_samples = sorted(samples)
            index = int(math.ceil(percentile / 100.0 * len(sorted_samples))) - 1
            index = max(0, min(index, len(sorted_samples) - 1))
            return sorted_samples[index]

    def get_summary(self) -> MetricsSummary:
        """Build a snapshot of all metrics as a ``MetricsSummary``."""
        with self._lock:
            total_reqs = self.calls_total.value
            total_errs = self.errors_total.value
            error_rate = total_errs / total_reqs if total_reqs > 0 else 0.0

            # Pooled latency stats
            all_lats = [
                ms
                for ep_samples in self._latencies.values()
                for ms in ep_samples
            ]
            avg_ms = sum(all_lats) / len(all_lats) if all_lats else 0.0
            p50 = self._percentile_from_list(all_lats, 50.0)
            p95 = self._percentile_from_list(all_lats, 95.0)
            p99 = self._percentile_from_list(all_lats, 99.0)

            # Per-endpoint summaries
            per_ep: dict[str, MetricsSummary] = {}
            for ep in set(
                list(self._request_counts.keys())
                + list(self._error_counts.keys())
            ):
                ep_reqs = self._request_counts.get(ep, 0)
                ep_errs = self._error_counts.get(ep, 0)
                ep_lats = self._latencies.get(ep, [])
                per_ep[ep] = MetricsSummary(
                    total_requests=ep_reqs,
                    total_errors=ep_errs,
                    error_rate=ep_errs / ep_reqs if ep_reqs > 0 else 0.0,
                    avg_latency_ms=sum(ep_lats) / len(ep_lats) if ep_lats else 0.0,
                    p50_ms=self._percentile_from_list(ep_lats, 50.0),
                    p95_ms=self._percentile_from_list(ep_lats, 95.0),
                    p99_ms=self._percentile_from_list(ep_lats, 99.0),
                )

            return MetricsSummary(
                total_requests=total_reqs,
                total_errors=total_errs,
                error_rate=error_rate,
                avg_latency_ms=avg_ms,
                p50_ms=p50,
                p95_ms=p95,
                p99_ms=p99,
                per_endpoint=per_ep,
            )

    def reset(self) -> None:
        """Clear all collected metrics."""
        with self._lock:
            self.calls_total = Counter(f"{self.prefix}_calls_total")
            self.errors_total = Counter(f"{self.prefix}_errors_total")
            self.retries_total = Counter(f"{self.prefix}_retries_total")
            self.latency_seconds = Histogram(f"{self.prefix}_latency_seconds")
            self.ws_disconnects_total = Counter(f"{self.prefix}_ws_disconnects_total")
            self.ws_reconnects_total = Counter(f"{self.prefix}_ws_reconnects_total")
            self.ws_messages_received = Counter(f"{self.prefix}_ws_messages_received")
            self._request_counts.clear()
            self._error_counts.clear()
            self._latencies.clear()

    @contextmanager
    def measure(self):
        """Context manager that records call duration.

        Increments ``errors_total`` if the body raises.
        """
        import time as _time
        start = _time.monotonic()
        try:
            yield
        except Exception:
            self.errors_total.inc()
            raise
        finally:
            self.latency_seconds.observe(_time.monotonic() - start)
            self.calls_total.inc()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _percentile_from_list(sorted_samples: list[float], percentile: float) -> float:
        """Return the *percentile* value from a *pre-sorted* list."""
        if not sorted_samples:
            return 0.0
        index = int(math.ceil(percentile / 100.0 * len(sorted_samples))) - 1
        index = max(0, min(index, len(sorted_samples) - 1))
        return sorted_samples[index]
