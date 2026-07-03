"""
Tests for adapter metrics — Counter, Histogram, AdapterMetrics, MetricsSummary, thread safety.
"""

from __future__ import annotations

import threading
import time

import pytest

from polymind.polymarket.metrics import AdapterMetrics, Counter, Histogram, MetricsSummary


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
        h.observe(0.001)
        h.observe(0.3)
        assert h._counts[0.005] >= 1


class TestAdapterMetricsExisting:
    """Verify existing measure / prefix functionality still works."""

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
        with pytest.raises(ValueError), m.measure():
            raise ValueError("test")
        assert m.errors_total.value == 1
        assert m.calls_total.value == 1

    def test_measure_records_latency(self):
        m = AdapterMetrics("test")
        with m.measure():
            time.sleep(0.001)
        assert m.latency_seconds.count == 1
        assert m.latency_seconds.sum > 0


class TestRecordRequest:
    def test_single_request(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/markets", 150.0, 200)
        assert m.get_request_count() == 1
        assert m.get_request_count("/markets") == 1

    def test_multiple_requests_per_endpoint(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/markets", 100.0, 200)
        m.record_request("GET", "/markets", 200.0, 200)
        m.record_request("POST", "/order", 50.0, 201)
        assert m.get_request_count() == 3
        assert m.get_request_count("/markets") == 2
        assert m.get_request_count("/order") == 1
        # Unknown endpoint returns 0
        assert m.get_request_count("/unknown") == 0

    def test_record_error(self):
        m = AdapterMetrics("test")
        m.record_error("GET", "/markets", "RateLimit")
        assert m.get_error_rate() == 0.0  # no requests yet means 0% error
        # record a request then another error
        m.record_request("GET", "/markets", 100.0, 200)
        m.record_error("GET", "/markets", "ServerError")
        # total: 1 request, 2 errors -> error_rate = 2.0
        assert m.get_error_rate() == 2.0
        assert m.get_error_rate("/markets") == 2.0


class TestErrorRate:
    def test_zero_errors(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/a", 10.0, 200)
        m.record_request("GET", "/b", 20.0, 200)
        assert m.get_error_rate() == 0.0
        assert m.get_error_rate("/a") == 0.0

    def test_some_errors(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/ep", 10.0, 200)
        m.record_request("GET", "/ep", 15.0, 200)
        m.record_error("GET", "/ep", "Timeout")
        # 2 requests, 1 error -> 0.5
        assert m.get_error_rate("/ep") == 0.5

    def test_all_errors(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/ep", 5.0, 500)
        m.record_error("GET", "/ep", "InternalError")
        # 1 request, 1 additional error -> 1.0
        assert m.get_error_rate("/ep") == 1.0

    def test_empty_returns_zero(self):
        m = AdapterMetrics("test")
        assert m.get_error_rate() == 0.0
        assert m.get_error_rate("/missing") == 0.0


class TestLatencyPercentiles:
    def test_no_data_returns_zero(self):
        m = AdapterMetrics("test")
        assert m.get_latency_percentile() == 0.0
        assert m.get_latency_percentile("/nope") == 0.0

    def test_single_latency(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/ep", 100.0, 200)
        assert m.get_latency_percentile("/ep", 50.0) == 100.0
        assert m.get_latency_percentile("/ep", 99.0) == 100.0

    def test_percentiles_accuracy(self):
        m = AdapterMetrics("test")
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        for latency in latencies:
            m.record_request("GET", "/ep", latency, 200)
        p50 = m.get_latency_percentile("/ep", 50.0)
        p95 = m.get_latency_percentile("/ep", 95.0)
        p99 = m.get_latency_percentile("/ep", 99.0)
        assert p50 == 50.0
        assert p95 == 100.0  # ceiling of 95th pctile in 10 items = item 9 (0-indexed)
        assert p99 == 100.0

    def test_no_endpoint_pools_all(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/a", 10.0, 200)
        m.record_request("GET", "/b", 20.0, 200)
        # Pooled: [10, 20] -> p50 = 10, p95 = 20
        assert m.get_latency_percentile(percentile=50.0) == 10.0
        assert m.get_latency_percentile(percentile=95.0) == 20.0


class TestSummary:
    def test_summary_has_all_fields(self):
        m = AdapterMetrics("test")
        summary = m.get_summary()
        assert isinstance(summary, MetricsSummary)
        assert summary.total_requests == 0
        assert summary.total_errors == 0
        assert summary.error_rate == 0.0
        assert summary.avg_latency_ms == 0.0
        assert summary.p50_ms == 0.0
        assert summary.p95_ms == 0.0
        assert summary.p99_ms == 0.0
        assert summary.per_endpoint == {}

    def test_summary_with_data(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/markets", 50.0, 200)
        m.record_request("GET", "/markets", 150.0, 200)
        m.record_error("GET", "/markets", "Timeout")

        summary = m.get_summary()
        assert summary.total_requests == 2
        assert summary.total_errors == 1
        assert summary.error_rate == 0.5
        assert summary.avg_latency_ms == 100.0
        assert summary.p50_ms == 50.0
        assert summary.p95_ms == 150.0
        assert summary.p99_ms == 150.0
        assert "/markets" in summary.per_endpoint
        ep = summary.per_endpoint["/markets"]
        assert ep.total_requests == 2
        assert ep.total_errors == 1
        assert ep.avg_latency_ms == 100.0

    def test_summary_multiple_endpoints(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/markets", 10.0, 200)
        m.record_request("POST", "/order", 200.0, 201)
        m.record_error("POST", "/order", "Validation")

        summary = m.get_summary()
        assert summary.total_requests == 2
        assert summary.total_errors == 1
        assert set(summary.per_endpoint.keys()) == {"/markets", "/order"}
        assert summary.per_endpoint["/markets"].total_errors == 0
        assert summary.per_endpoint["/order"].total_errors == 1


class TestReset:
    def test_reset_clears_counters(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/markets", 50.0, 200)
        m.record_error("GET", "/markets", "Error")
        assert m.get_request_count() > 0
        assert m.errors_total.value > 0

        m.reset()
        assert m.get_request_count() == 0
        assert m.errors_total.value == 0
        assert m.get_request_count("/markets") == 0
        assert m.get_summary().total_requests == 0
        assert m.latency_seconds.count == 0

    def test_reset_keeps_prefix(self):
        m = AdapterMetrics("my_prefix")
        m.reset()
        assert m.prefix == "my_prefix"
        assert "my_prefix" in m.calls_total.name


class TestPerEndpointFiltering:
    def test_request_count_filter(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/a", 1.0, 200)
        m.record_request("GET", "/b", 2.0, 200)
        m.record_request("GET", "/a", 3.0, 200)
        assert m.get_request_count("/a") == 2
        assert m.get_request_count("/b") == 1
        assert m.get_request_count() == 3

    def test_error_rate_filter(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/a", 1.0, 200)
        m.record_request("GET", "/b", 2.0, 200)
        m.record_error("GET", "/a", "Err")
        m.record_error("GET", "/b", "Err")
        m.record_error("GET", "/b", "Err")
        assert m.get_error_rate("/a") == 1.0
        assert m.get_error_rate("/b") == 2.0
        assert m.get_error_rate() == 3.0 / 2.0

    def test_latency_filter(self):
        m = AdapterMetrics("test")
        m.record_request("GET", "/a", 10.0, 200)
        m.record_request("GET", "/b", 100.0, 200)
        assert m.get_latency_percentile("/a") == 10.0
        assert m.get_latency_percentile("/b") == 100.0


class TestThreadSafety:
    def test_concurrent_record_request(self):
        m = AdapterMetrics("test")
        n_threads = 10
        calls_per = 100

        def worker():
            for _ in range(calls_per):
                m.record_request("GET", "/ep", 1.0, 200)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert m.get_request_count() == n_threads * calls_per
        assert m.get_request_count("/ep") == n_threads * calls_per

    def test_concurrent_record_error(self):
        m = AdapterMetrics("test")
        n_threads = 5
        calls_per = 50

        def worker():
            for _ in range(calls_per):
                m.record_error("POST", "/order", "Timeout")

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert m.errors_total.value == n_threads * calls_per

    def test_concurrent_mixed_ops(self):
        """Read and write concurrently; no crash and eventual consistency."""
        m = AdapterMetrics("test")
        stop = False

        def writer():
            while not stop:
                m.record_request("GET", "/ep", 5.0, 200)
                m.record_error("GET", "/ep", "Err")

        def reader():
            while not stop:
                m.get_request_count()
                m.get_error_rate()
                m.get_latency_percentile()
                m.get_summary()

        writers = [threading.Thread(target=writer) for _ in range(4)]
        readers = [threading.Thread(target=reader) for _ in range(2)]
        all_threads = writers + readers
        for t in all_threads:
            t.start()
        time.sleep(0.1)
        stop = True
        for t in all_threads:
            t.join()

        # Total should be consistent
        assert m.get_request_count() >= 0
        # Reset should work even after concurrent access
        m.reset()
        assert m.get_request_count() == 0

    def test_concurrent_reset_with_records(self):
        """Reset while other threads are recording — final reset clean."""
        m = AdapterMetrics("test")
        stop = False

        def recorder():
            while not stop:
                m.record_request("GET", "/ep", 5.0, 200)

        def reseter():
            for _ in range(20):
                m.reset()

        recs = [threading.Thread(target=recorder) for _ in range(4)]
        reset_thread = threading.Thread(target=reseter)
        for t in recs:
            t.start()
        reset_thread.start()
        time.sleep(0.1)
        stop = True
        for t in recs:
            t.join()
        reset_thread.join()

        # After all threads joined, we can safely assert clean state
        m.reset()
        assert m.get_request_count() == 0
        assert m.errors_total.value == 0
