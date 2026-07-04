"""
CLOB SDK adapter conformance validation.

Verifies that the Polymarket adapter implementations satisfy the
contracts defined in the architecture spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConformanceResult:
    check_name: str
    passed: bool
    message: str = ""

    def __bool__(self) -> bool:
        return self.passed


@dataclass
class ConformanceReport:
    results: list[ConformanceResult] = field(default_factory=list)
    adapter_name: str = ""

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def summary(self) -> str:
        total = len(self.results)
        good = sum(1 for r in self.results if r.passed)
        return f"{self.adapter_name}: {good}/{total} checks passed"


def check_polymarket_client() -> list[ConformanceResult]:
    from polymind.polymarket.client import PolymarketClient

    results: list[ConformanceResult] = []

    # Check client has required methods
    for method in ["connect", "close", "get_markets", "get_order_book", "get_market"]:
        results.append(
            ConformanceResult(
                check_name=f"client.{method}",
                passed=hasattr(PolymarketClient, method),
                message=f"{'Found' if hasattr(PolymarketClient, method) else 'Missing'} {method}",
            )
        )
    return results


def check_contracts_gateway() -> list[ConformanceResult]:
    from polymind.polymarket.contracts import ContractsGateway

    results: list[ConformanceResult] = []
    for method in ["split", "merge", "redeem", "get_onchain_balance", "approve_usdc"]:
        results.append(
            ConformanceResult(
                check_name=f"gateway.{method}",
                passed=hasattr(ContractsGateway, method),
                message=f"{'Found' if hasattr(ContractsGateway, method) else 'Missing'} {method}",
            )
        )
    return results


def check_websocket() -> list[ConformanceResult]:
    from polymind.polymarket.websocket import PolymarketWebSocketAdapter

    results: list[ConformanceResult] = []
    for method in ["connect", "subscribe", "close"]:
        results.append(
            ConformanceResult(
                check_name=f"websocket.{method}",
                passed=hasattr(PolymarketWebSocketAdapter, method),
                message=f"{'Found' if hasattr(PolymarketWebSocketAdapter, method) else 'Missing'} {method}",
            )
        )
    return results


def check_signer() -> list[ConformanceResult]:
    from polymind.polymarket.signer import Signer

    results: list[ConformanceResult] = []
    for method in ["sign_typed_data", "sign_hash", "can_sign", "derive_api_key"]:
        results.append(
            ConformanceResult(
                check_name=f"signer.{method}",
                passed=hasattr(Signer, method),
                message=f"{'Found' if hasattr(Signer, method) else 'Missing'} {method}",
            )
        )
    return results


def run_all_checks(adapter_name: str = "polymarket") -> ConformanceReport:
    """Run all conformance checks for the Polymarket adapter layer."""
    report = ConformanceReport(adapter_name=adapter_name)
    for check_fn in [
        check_polymarket_client,
        check_contracts_gateway,
        check_websocket,
        check_signer,
    ]:
        report.results.extend(check_fn())
    return report
