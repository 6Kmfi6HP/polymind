"""Pre-flight checks for Polymind deployment readiness."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto


class PreflightSeverity(Enum):
    PASS = auto()
    WARN = auto()
    FAIL = auto()


@dataclass
class PreflightResult:
    check_name: str
    passed: bool
    message: str = ""
    severity: PreflightSeverity = PreflightSeverity.FAIL


@dataclass
class PreflightReport:
    passed: bool
    results: list[PreflightResult]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PreflightChecker:
    """Runs deployment-readiness checks."""

    @staticmethod
    def check_config(config_dict: dict, required_keys: list[str]) -> PreflightResult:
        """Validate that the configuration contains all required keys.

        Args:
            config_dict: The configuration dictionary to validate.
            required_keys: List of keys that must be present and non-None.

        Returns:
            A ``PreflightResult`` with ``passed=True`` and severity ``PASS``
            when all required keys are present, or ``passed=False`` with
            severity ``FAIL`` if any are missing.
        """
        missing = [k for k in required_keys if k not in config_dict or config_dict[k] is None]
        if missing:
            return PreflightResult(
                check_name="config",
                passed=False,
                message=f"Missing required config keys: {', '.join(missing)}",
                severity=PreflightSeverity.FAIL,
            )
        return PreflightResult(
            check_name="config",
            passed=True,
            message="All required config keys are present",
            severity=PreflightSeverity.PASS,
        )

    @staticmethod
    def check_credentials(has_api_key: bool, has_private_key: bool) -> PreflightResult:
        """Verify that required credentials are available.

        Args:
            has_api_key: Whether an API key is set.
            has_private_key: Whether a private key is set.

        Returns:
            A ``PreflightResult`` with ``passed=True`` and severity ``PASS``
            when both credentials are present; ``passed=False`` with severity
            ``WARN`` when one is missing; ``passed=False`` with severity
            ``FAIL`` when both are missing.
        """
        if not has_api_key and not has_private_key:
            return PreflightResult(
                check_name="credentials",
                passed=False,
                message="Both API key and private key are missing",
                severity=PreflightSeverity.FAIL,
            )
        if not has_api_key:
            return PreflightResult(
                check_name="credentials",
                passed=False,
                message="API key is missing",
                severity=PreflightSeverity.WARN,
            )
        if not has_private_key:
            return PreflightResult(
                check_name="credentials",
                passed=False,
                message="Private key is missing",
                severity=PreflightSeverity.WARN,
            )
        return PreflightResult(
            check_name="credentials",
            passed=True,
            message="All credentials are present",
            severity=PreflightSeverity.PASS,
        )

    @staticmethod
    def check_connectivity(test_url: str, timeout: float = 10.0) -> PreflightResult:
        """Check connectivity to an external service.

        Attempts an HTTP GET to ``test_url`` and returns ``PASS`` on a
        successful response, ``FAIL`` on failure or exception.

        Args:
            test_url: URL to test against.
            timeout: Request timeout in seconds.

        Returns:
            A ``PreflightResult`` indicating connectivity status.
        """
        import httpx

        try:
            response = httpx.get(test_url, timeout=timeout)
            if response.is_success:
                return PreflightResult(
                    check_name="connectivity",
                    passed=True,
                    message=f"Successfully connected to {test_url}",
                    severity=PreflightSeverity.PASS,
                )
            return PreflightResult(
                check_name="connectivity",
                passed=False,
                message=f"Received status {response.status_code} from {test_url}",
                severity=PreflightSeverity.FAIL,
            )
        except Exception as exc:
            return PreflightResult(
                check_name="connectivity",
                passed=False,
                message=f"Connection to {test_url} failed: {exc}",
                severity=PreflightSeverity.FAIL,
            )

    @staticmethod
    def run_all(config: dict, has_api_key: bool, has_private_key: bool) -> PreflightReport:
        """Run all standard pre-flight checks and return an aggregated report.

        Runs ``check_config`` (with default required keys ``platform`` and
        ``initial_capital``) and ``check_credentials``.

        Args:
            config: The configuration dictionary to validate.
            has_api_key: Whether an API key is set.
            has_private_key: Whether a private key is set.

        Returns:
            A ``PreflightReport`` containing every check result.
        """
        required_keys = ["platform", "initial_capital"]
        results = [
            PreflightChecker.check_config(config, required_keys),
            PreflightChecker.check_credentials(has_api_key, has_private_key),
        ]
        passed = all(r.passed for r in results)
        return PreflightReport(passed=passed, results=results)
