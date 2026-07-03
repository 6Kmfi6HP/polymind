"""
Tests for adapter metrics.
"""

from __future__ import annotations

import time

import pytest

from polymind.polymarket.metrics import AdapterMetrics, Counter, Histogram


class TestCounter:
    def test_init_zero(self):
        c = Counter("test")
        assert c.value == 0

    def test_inc(self):
        c = Counter("test")
        c.inc()
        assert c.value == 1

    def test_inc_multiple(self):
        c = Counter("test")
        c.inc(5)
        assert c.value == 5


class TestHistogram:
    def test_observe_increments_count(self):
        h = Histogram("test")
        h.observe(0.1)
        assert h.count == 1

    def test_observe_records_sum(self):
        h = Histogram("test")
        h.observe(0.5)
        h.observe(1.5)
        assert h.sum == pytest.approx(2.0)

    def test_observe_bucket_counts(self):
        h = Histogram("test")
        h.observe(0.001)  # falls in first bucket
        h.observe(0.3)    # falls in middle bucket
        assert h._counts[0.005] >= 1  # first observation hits



class TestAdapterMetrics:
    def test_prefix(self):
        m = AdapterMetrics("test_prefix")
        assert m.prefix == "test_prefix"
        assert "test_prefix" in m.calls_total.name

    def test_counter_defaults_zero(self):
        m = AdapterMetrics("test")
        assert m.calls_total.value == 0
        assert m.errors_total.value == 0

    def test_measure_success(self):
        m = AdapterMetrics("test")
        with m.measure():
            pass
        assert m.calls_total.value == 1
        assert m.errors_total.value == 0

    def test_measure_increments_errors_on_exception(self):
        m = AdapterMetrics("test")
        with pytest.raises(ValueError):
            with m.measure():
                raise ValueError("test")
        assert m.errors_total.value == 1
        assert m.calls_total.value == 1

    def test_measure_records_latency(self):
        m = AdapterMetrics("test")
        with m.measure():
            time.sleep(0.001)
        assert m.latency_seconds.count == 1
        assert m.latency_seconds.sum > 0
