"""
Tests for CLOB adapter conformance validation.
"""

from __future__ import annotations

from polymind.cli.conformance import (
    ConformanceReport,
    ConformanceResult,
    check_contracts_gateway,
    check_polymarket_client,
    check_signer,
    check_websocket,
    run_all_checks,
)


class TestConformanceResult:
    def test_passed_bool(self):
        assert ConformanceResult("test", passed=True)
        assert not ConformanceResult("test", passed=False)

    def test_message(self):
        r = ConformanceResult("test", passed=False, message="missing")
        assert "missing" in r.message


class TestConformanceReport:
    def test_all_pass(self):
        report = ConformanceReport(
            results=[ConformanceResult("a", True), ConformanceResult("b", True)],
        )
        assert report.passed is True

    def test_any_fail(self):
        report = ConformanceReport(
            results=[ConformanceResult("a", True), ConformanceResult("b", False)],
        )
        assert report.passed is False


class TestChecks:
    def test_check_client(self):
        results = check_polymarket_client()
        assert len(results) >= 3
        assert all(r.passed for r in results)

    def test_check_gateway(self):
        results = check_contracts_gateway()
        assert len(results) >= 5
        assert all(r.passed for r in results)

    def test_check_websocket(self):
        results = check_websocket()
        assert len(results) >= 3
        assert all(r.passed for r in results)

    def test_check_signer(self):
        results = check_signer()
        assert len(results) >= 3
        assert all(r.passed for r in results)

    def test_run_all(self):
        report = run_all_checks()
        total = len(report.results)
        assert total >= 14
        assert report.passed is True
