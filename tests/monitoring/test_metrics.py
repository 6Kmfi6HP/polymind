"""Tests for the monitoring metrics collector."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.monitoring.metrics import MetricsCollector, MetricsSnapshot


class TestMetricsCollector:
    @pytest.fixture
    def collector(self) -> MetricsCollector:
        return MetricsCollector()

    def test_initial_state(self, collector: MetricsCollector) -> None:
        snapshot = collector.snapshot()
        assert snapshot.orders_placed == 0
        assert snapshot.orders_filled == 0
        assert snapshot.orders_cancelled == 0
        assert snapshot.errors == 0
        assert snapshot.total_pnl == 0.0

    def test_increment_order_placed(self, collector: MetricsCollector) -> None:
        collector.record_order_placed()
        assert collector.snapshot().orders_placed == 1
        collector.record_order_placed(3)
        assert collector.snapshot().orders_placed == 4

    def test_increment_fill(self, collector: MetricsCollector) -> None:
        collector.record_fill()
        assert collector.snapshot().orders_filled == 1
        collector.record_fill(5)
        assert collector.snapshot().orders_filled == 6

    def test_increment_cancellation(self, collector: MetricsCollector) -> None:
        collector.record_cancellation()
        assert collector.snapshot().orders_cancelled == 1

    def test_increment_error(self, collector: MetricsCollector) -> None:
        collector.record_error()
        assert collector.snapshot().errors == 1
        collector.record_error(3)
        assert collector.snapshot().errors == 4

    def test_record_pnl(self, collector: MetricsCollector) -> None:
        collector.record_pnl(50.0)
        assert collector.snapshot().total_pnl == 50.0
        collector.record_pnl(-10.0)
        assert collector.snapshot().total_pnl == 40.0

    def test_record_latency(self, collector: MetricsCollector) -> None:
        collector.record_latency(0.15)
        collector.record_latency(0.25)
        collector.record_latency(0.35)
        snap = collector.snapshot()
        assert snap.avg_latency_ms is not None
        assert snap.avg_latency_ms == pytest.approx(0.25, rel=1e-3)
        assert snap.min_latency_ms == pytest.approx(0.15, rel=1e-3)
        assert snap.max_latency_ms == pytest.approx(0.35, rel=1e-3)

    def test_latency_without_records(self, collector: MetricsCollector) -> None:
        snap = collector.snapshot()
        assert snap.avg_latency_ms is None
        assert snap.min_latency_ms is None
        assert snap.max_latency_ms is None

    def test_timestamp_on_snapshot(self, collector: MetricsCollector) -> None:
        before = datetime.now(timezone.utc)
        snap = collector.snapshot()
        after = datetime.now(timezone.utc)
        assert before <= snap.timestamp <= after

    def test_up_time(self, collector: MetricsCollector) -> None:
        snap1 = collector.snapshot()
        snap2 = collector.snapshot()
        assert snap2.up_time_seconds >= snap1.up_time_seconds

    def test_multiple_snapshots_cumulative(self, collector: MetricsCollector) -> None:
        collector.record_order_placed(10)
        collector.record_fill(7)
        collector.record_cancellation(2)
        collector.record_error(1)
        collector.record_pnl(100.0)
        collector.record_latency(0.5)

        snap = collector.snapshot()
        assert snap.orders_placed == 10
        assert snap.orders_filled == 7
        assert snap.orders_cancelled == 2
        assert snap.errors == 1
        assert snap.total_pnl == 100.0

    def test_reset(self, collector: MetricsCollector) -> None:
        collector.record_order_placed(10)
        collector.record_pnl(500.0)
        collector.reset()
        snap = collector.snapshot()
        assert snap.orders_placed == 0
        assert snap.total_pnl == 0.0

    def test_str_representation(self, collector: MetricsCollector) -> None:
        collector.record_order_placed(5)
        collector.record_fill(3)
        text = str(collector)
        assert "orders_placed=5" in text
        assert "orders_filled=3" in text

    def test_merge_snapshots(self, collector: MetricsCollector) -> None:
        collector.record_order_placed(3)
        collector.record_pnl(75.0)

        other = MetricsCollector()
        other.record_order_placed(2)
        other.record_pnl(25.0)

        merged = collector.merge(other)
        assert merged.orders_placed == 5
        assert merged.total_pnl == 100.0

    def test_merge_with_empty(self, collector: MetricsCollector) -> None:
        other = MetricsCollector()
        collector.record_order_placed(7)
        merged = collector.merge(other)
        assert merged.orders_placed == 7


class TestMetricsSnapshot:
    def test_fill_rate(self) -> None:
        snap = MetricsSnapshot(
            timestamp=datetime.now(timezone.utc),
            orders_placed=10,
            orders_filled=5,
        )
        assert snap.fill_rate == 0.5

    def test_fill_rate_no_orders(self) -> None:
        snap = MetricsSnapshot(
            timestamp=datetime.now(timezone.utc),
            orders_placed=0,
            orders_filled=0,
        )
        assert snap.fill_rate == 0.0

    def test_error_rate(self) -> None:
        snap = MetricsSnapshot(
            timestamp=datetime.now(timezone.utc),
            orders_placed=100,
            errors=5,
        )
        assert snap.error_rate == 0.05

    def test_error_rate_no_orders(self) -> None:
        snap = MetricsSnapshot(
            timestamp=datetime.now(timezone.utc),
        )
        assert snap.error_rate == 0.0

    def test_cancellation_rate(self) -> None:
        snap = MetricsSnapshot(
            timestamp=datetime.now(timezone.utc),
            orders_placed=20,
            orders_cancelled=4,
        )
        assert snap.cancellation_rate == 0.2

    def test_to_dict(self) -> None:
        ts = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)
        snap = MetricsSnapshot(
            timestamp=ts,
            orders_placed=10,
            orders_filled=7,
            orders_cancelled=1,
            errors=0,
            total_pnl=150.0,
            avg_latency_ms=0.25,
            min_latency_ms=0.1,
            max_latency_ms=0.5,
            up_time_seconds=3600.0,
        )
        d = snap.to_dict()
        assert d["orders_placed"] == 10
        assert d["orders_filled"] == 7
        assert d["total_pnl"] == 150.0
        assert d["fill_rate"] == 0.7
        assert d["timestamp"] == "2026-07-05T12:00:00+00:00"

    def test_to_dict_empty(self) -> None:
        snap = MetricsSnapshot(timestamp=datetime.now(timezone.utc))
        d = snap.to_dict()
        assert d["orders_placed"] == 0
        assert d["orders_filled"] == 0
