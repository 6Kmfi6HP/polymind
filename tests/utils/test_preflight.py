"""Tests for polymind.utils.preflight."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from polymind.utils.preflight import (
    PreflightChecker,
    PreflightReport,
    PreflightResult,
    PreflightSeverity,
)


class TestPreflightSeverity:
    def test_enum_values(self):
        assert isinstance(PreflightSeverity.PASS, PreflightSeverity)
        assert isinstance(PreflightSeverity.WARN, PreflightSeverity)
        assert isinstance(PreflightSeverity.FAIL, PreflightSeverity)

    def test_enum_distinct(self):
        assert PreflightSeverity.PASS != PreflightSeverity.WARN
        assert PreflightSeverity.PASS != PreflightSeverity.FAIL
        assert PreflightSeverity.WARN != PreflightSeverity.FAIL


class TestPreflightResult:
    def test_minimal_construction(self):
        result = PreflightResult(check_name="test", passed=True)
        assert result.check_name == "test"
        assert result.passed is True
        assert result.message == ""
        assert result.severity == PreflightSeverity.FAIL

    def test_full_construction(self):
        result = PreflightResult(
            check_name="full_test",
            passed=False,
            message="Something went wrong",
            severity=PreflightSeverity.WARN,
        )
        assert result.check_name == "full_test"
        assert result.passed is False
        assert result.message == "Something went wrong"
        assert result.severity == PreflightSeverity.WARN


class TestPreflightReport:
    def test_construction(self):
        results = [
            PreflightResult(check_name="a", passed=True),
            PreflightResult(check_name="b", passed=False),
        ]
        report = PreflightReport(passed=False, results=results)
        assert report.passed is False
        assert len(report.results) == 2
        assert isinstance(report.timestamp, datetime)

    def test_default_timestamp_is_set(self):
        report = PreflightReport(passed=True, results=[])
        assert report.timestamp is not None
        assert isinstance(report.timestamp, datetime)


class TestCheckConfig:
    def test_all_present_passes(self):
        result = PreflightChecker.check_config(
            {"platform": "polymarket", "initial_capital": 1000},
            ["platform", "initial_capital"],
        )
        assert result.passed is True
        assert result.severity == PreflightSeverity.PASS

    def test_missing_key_fails(self):
        result = PreflightChecker.check_config(
            {"platform": "polymarket"},
            ["platform", "initial_capital"],
        )
        assert result.passed is False
        assert result.severity == PreflightSeverity.FAIL
        assert "initial_capital" in result.message

    def test_multiple_missing(self):
        result = PreflightChecker.check_config({}, ["a", "b", "c"])
        assert result.passed is False
        assert "a, b, c" in result.message

    def test_none_value_treated_as_missing(self):
        result = PreflightChecker.check_config(
            {"platform": "polymarket", "initial_capital": None},
            ["platform", "initial_capital"],
        )
        assert result.passed is False
        assert "initial_capital" in result.message

    def test_passes_with_empty_required_keys(self):
        result = PreflightChecker.check_config({"anything": 1}, [])
        assert result.passed is True
        assert result.severity == PreflightSeverity.PASS


class TestCheckCredentials:
    def test_both_present_passes(self):
        result = PreflightChecker.check_credentials(has_api_key=True, has_private_key=True)
        assert result.passed is True
        assert result.severity == PreflightSeverity.PASS

    def test_both_missing_fails(self):
        result = PreflightChecker.check_credentials(has_api_key=False, has_private_key=False)
        assert result.passed is False
        assert result.severity == PreflightSeverity.FAIL
        assert "Both" in result.message

    def test_missing_api_key_warns(self):
        result = PreflightChecker.check_credentials(has_api_key=False, has_private_key=True)
        assert result.passed is False
        assert result.severity == PreflightSeverity.WARN
        assert "API key" in result.message

    def test_missing_private_key_warns(self):
        result = PreflightChecker.check_credentials(has_api_key=True, has_private_key=False)
        assert result.passed is False
        assert result.severity == PreflightSeverity.WARN
        assert "Private key" in result.message


class TestCheckConnectivity:
    def test_successful_connection(self):
        with patch("httpx.get") as mock_get:
            mock_response = mock_get.return_value
            mock_response.is_success = True

            result = PreflightChecker.check_connectivity(
                test_url="https://example.com", timeout=5.0
            )
            assert result.passed is True
            assert result.severity == PreflightSeverity.PASS
            mock_get.assert_called_once_with("https://example.com", timeout=5.0)

    def test_failed_status_code(self):
        with patch("httpx.get") as mock_get:
            mock_response = mock_get.return_value
            mock_response.is_success = False
            mock_response.status_code = 503

            result = PreflightChecker.check_connectivity(
                test_url="https://example.com", timeout=5.0
            )
            assert result.passed is False
            assert result.severity == PreflightSeverity.FAIL
            assert "503" in result.message

    def test_connection_exception(self):
        with patch("httpx.get", side_effect=Exception("Connection refused")):
            result = PreflightChecker.check_connectivity(
                test_url="https://example.com", timeout=5.0
            )
            assert result.passed is False
            assert result.severity == PreflightSeverity.FAIL
            assert "Connection refused" in result.message


class TestRunAll:
    def test_returns_report(self):
        report = PreflightChecker.run_all(
            config={"platform": "p", "initial_capital": 1},
            has_api_key=True,
            has_private_key=True,
        )
        assert isinstance(report, PreflightReport)
        assert len(report.results) == 2

    def test_report_passed_when_all_pass(self):
        report = PreflightChecker.run_all(
            config={"platform": "p", "initial_capital": 1},
            has_api_key=True,
            has_private_key=True,
        )
        assert report.passed is True
        for r in report.results:
            assert r.passed is True

    def test_report_failed_when_config_fails(self):
        report = PreflightChecker.run_all(
            config={"platform": "p"},
            has_api_key=True,
            has_private_key=True,
        )
        assert report.passed is False

    def test_report_failed_when_credentials_fail(self):
        report = PreflightChecker.run_all(
            config={"platform": "p", "initial_capital": 1},
            has_api_key=False,
            has_private_key=False,
        )
        assert report.passed is False

    def test_report_failed_when_both_fail(self):
        report = PreflightChecker.run_all(
            config={},
            has_api_key=False,
            has_private_key=False,
        )
        assert report.passed is False
