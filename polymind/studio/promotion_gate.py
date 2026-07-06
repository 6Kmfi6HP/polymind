"""
Factor promotion gate — enforces all evidence requirements before a factor
can be approved for production.

Each factor must pass a set of checks before it is promoted:

  1. Executable price backtest
  2. Walk-forward validation
  3. Bootstrap / confidence interval evidence
  4. Paper OMS execution
  5. Capacity analysis
  6. Execution sensitivity report
  7. Failure analysis

Usage::

    gate = FactorPromotionGate()
    report = gate.check(factor_card, backtest_result, walk_forward_result)
    if report.all_checks_passed:
        factor_card.approved = True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CapacityAnalysis:
    """Analysis of a factor's market capacity.

    Parameters
    ----------
    max_capital_usd:
        Estimated maximum deployable capital before alpha decay.
    avg_daily_volume_usd:
        Average daily notional volume across traded markets.
    market_impact_bps:
        Estimated market impact in basis points at target size.
    capacity_rating:
        Qualitative rating: "high", "medium", "low", or "unknown".
    """

    max_capital_usd: float = 0.0
    avg_daily_volume_usd: float = 0.0
    market_impact_bps: float = 0.0
    capacity_rating: str = "unknown"


@dataclass
class ExecutionSensitivityReport:
    """Analysis of execution cost sensitivity for a factor.

    Parameters
    ----------
    spread_impact_bps:
        Estimated cost from bid-ask spread in basis points.
    slippage_impact_bps:
        Estimated cost from market slippage in basis points.
    latency_sensitivity:
        Qualitative sensitivity to latency: "low", "medium", "high", or "unknown".
    total_execution_cost_bps:
        Total estimated execution cost in basis points (spread + slippage + fees).
    """

    spread_impact_bps: float = 0.0
    slippage_impact_bps: float = 0.0
    latency_sensitivity: str = "unknown"
    total_execution_cost_bps: float = 0.0


@dataclass
class FailureAnalysis:
    """Analysis of failure modes and downside risks for a factor.

    Parameters
    ----------
    failure_modes:
        Identified failure modes (e.g., "regime_change", "liquidity_crisis").
    worst_case_drawdown:
        Maximum observed or simulated drawdown.
    regime_sensitivity:
        Qualitative sensitivity to market regimes: "low", "medium", "high", or "unknown".
    """

    failure_modes: list[str] = field(default_factory=list)
    worst_case_drawdown: float = 0.0
    regime_sensitivity: str = "unknown"


@dataclass
class PromotionCheckReport:
    """Report card produced by FactorPromotionGate.check().

    Contains the pass/fail status for each of the seven evidence
    requirements along with optional nested analysis reports.

    Parameters
    ----------
    factor_name:
        Name of the factor being evaluated.
    executable_price_backtest:
        Whether a complete price backtest was run successfully.
    walk_forward_passed:
        Whether walk-forward validation produced positive results.
    bootstrap_confidence_passed:
        Whether bootstrap / confidence-interval analysis passed.
    paper_oms_passed:
        Whether paper OMS execution produced acceptable results.
    capacity_analysis_passed:
        Whether capacity analysis shows sufficient headroom.
    execution_sensitivity_passed:
        Whether execution sensitivity analysis was completed.
    failure_analysis_passed:
        Whether failure mode analysis was completed.
    capacity:
        Optional nested capacity analysis report.
    execution_sensitivity:
        Optional nested execution sensitivity report.
    failure_analysis:
        Optional nested failure analysis report.
    outcome:
        Overall outcome: "pass", "fail", "no_edge", or "inconclusive".
    details:
        Free-text details or explanation of the outcome.
    """

    factor_name: str = ""

    # Seven evidence checks
    executable_price_backtest: bool = False
    walk_forward_passed: bool = False
    bootstrap_confidence_passed: bool = False
    paper_oms_passed: bool = False
    capacity_analysis_passed: bool = False
    execution_sensitivity_passed: bool = False
    failure_analysis_passed: bool = False

    # Nested analysis reports
    capacity: CapacityAnalysis | None = None
    execution_sensitivity: ExecutionSensitivityReport | None = None
    failure_analysis: FailureAnalysis | None = None

    # Overall outcome
    outcome: str = "inconclusive"
    details: str = ""

    @property
    def all_checks_passed(self) -> bool:
        """True when all seven evidence requirements are met."""
        return (
            self.executable_price_backtest
            and self.walk_forward_passed
            and self.bootstrap_confidence_passed
            and self.paper_oms_passed
            and self.capacity_analysis_passed
            and self.execution_sensitivity_passed
            and self.failure_analysis_passed
        )

    @property
    def passed_checks(self) -> int:
        """Number of evidence checks that passed."""
        return sum(
            [
                self.executable_price_backtest,
                self.walk_forward_passed,
                self.bootstrap_confidence_passed,
                self.paper_oms_passed,
                self.capacity_analysis_passed,
                self.execution_sensitivity_passed,
                self.failure_analysis_passed,
            ]
        )

    @property
    def total_checks(self) -> int:
        """Total number of evidence checks (always 7)."""
        return 7

    @property
    def summary(self) -> str:
        """One-line summary of the promotion check report."""
        status = "PASS" if self.all_checks_passed else "FAIL"
        return (
            f"[{status}] {self.factor_name}: "
            f"{self.passed_checks}/{self.total_checks} checks passed, "
            f"outcome={self.outcome}"
        )


class FactorPromotionGate:
    """Gate that enforces all evidence requirements before promotion.

    The gate evaluates a factor against seven mandatory checks and
    produces a PromotionCheckReport. Only factors that pass all checks
    should have their ``approved`` flag set to ``True``.
    """

    def check(
        self,
        factor_card: Any = None,
        backtest_result: Any = None,
        walk_forward_result: Any = None,
        capacity: CapacityAnalysis | None = None,
        execution_sensitivity: ExecutionSensitivityReport | None = None,
        failure_analysis: FailureAnalysis | None = None,
        bootstrap_confidence_passed: bool = False,
        paper_oms_passed: bool = False,
    ) -> PromotionCheckReport:
        """Evaluate a factor against all seven promotion checks.

        Parameters
        ----------
        factor_card:
            A FactorCard-like object with at least a ``definition.name``
            attribute and a ``sharpe`` attribute.
        backtest_result:
            A FactorBacktestResult-like object with a ``sharpe`` attribute.
            If provided and ``sharpe > 0``, the executable-price-backtest
            check passes.
        walk_forward_result:
            A WalkForwardResult-like object with ``sharpe_consistency``
            and ``sharpe_mean`` attributes.
        capacity:
            Optional CapacityAnalysis. The capacity check passes when
            provided and ``capacity_rating`` is ``"high"`` or ``"medium"``.
        execution_sensitivity:
            Optional ExecutionSensitivityReport. The check passes when
            provided (not None).
        failure_analysis:
            Optional FailureAnalysis. The check passes when
            provided (not None).
        bootstrap_confidence_passed:
            Whether bootstrap / confidence-interval analysis passed.
        paper_oms_passed:
            Whether paper OMS execution passed.

        Returns
        -------
        PromotionCheckReport
            Full report with per-check status and nested analyses.
        """
        factor_name = self._get_factor_name(factor_card)

        # Check 1: executable price backtest
        executable_price_backtest = (
            backtest_result is not None
            and hasattr(backtest_result, "sharpe")
            and backtest_result.sharpe > 0.0
        )

        # Check 2: walk-forward
        walk_forward_passed = self._check_walk_forward(walk_forward_result)

        # Checks 3-4: passed in as booleans
        bootstrap_confidence_passed = bool(bootstrap_confidence_passed)
        paper_oms_passed = bool(paper_oms_passed)

        # Check 5: capacity analysis
        capacity_analysis_passed = capacity is not None and capacity.capacity_rating in (
            "high",
            "medium",
        )

        # Check 6: execution sensitivity
        execution_sensitivity_passed = execution_sensitivity is not None

        # Check 7: failure analysis
        failure_analysis_passed = failure_analysis is not None

        # Determine overall outcome
        outcome = self._determine_outcome(
            executable_price_backtest=executable_price_backtest,
            walk_forward_passed=walk_forward_passed,
            bootstrap_confidence_passed=bootstrap_confidence_passed,
            paper_oms_passed=paper_oms_passed,
            capacity_analysis_passed=capacity_analysis_passed,
            execution_sensitivity_passed=execution_sensitivity_passed,
            failure_analysis_passed=failure_analysis_passed,
        )

        return PromotionCheckReport(
            factor_name=factor_name,
            executable_price_backtest=executable_price_backtest,
            walk_forward_passed=walk_forward_passed,
            bootstrap_confidence_passed=bootstrap_confidence_passed,
            paper_oms_passed=paper_oms_passed,
            capacity_analysis_passed=capacity_analysis_passed,
            execution_sensitivity_passed=execution_sensitivity_passed,
            failure_analysis_passed=failure_analysis_passed,
            capacity=capacity,
            execution_sensitivity=execution_sensitivity,
            failure_analysis=failure_analysis,
            outcome=outcome,
        )

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _get_factor_name(factor_card: Any) -> str:
        """Extract the factor name from a card-like object."""
        if factor_card is None:
            return "unknown"
        if hasattr(factor_card, "definition") and hasattr(factor_card.definition, "name"):
            return factor_card.definition.name
        if hasattr(factor_card, "name"):
            return factor_card.name
        return "unknown"

    @staticmethod
    def _check_walk_forward(walk_forward_result: Any) -> bool:
        """Check whether walk-forward results are positive."""
        if walk_forward_result is None:
            return False
        if not hasattr(walk_forward_result, "sharpe_consistency"):
            return False
        if not hasattr(walk_forward_result, "sharpe_mean"):
            return False
        return walk_forward_result.sharpe_consistency > 0 and walk_forward_result.sharpe_mean > 0

    @staticmethod
    def _determine_outcome(
        executable_price_backtest: bool,
        walk_forward_passed: bool,
        bootstrap_confidence_passed: bool,
        paper_oms_passed: bool,
        capacity_analysis_passed: bool,
        execution_sensitivity_passed: bool,
        failure_analysis_passed: bool,
    ) -> str:
        """Determine the overall outcome from the seven check results.

        Returns
        -------
        str
            One of "pass", "inconclusive", or "no_edge".
        """
        all_checks = [
            executable_price_backtest,
            walk_forward_passed,
            bootstrap_confidence_passed,
            paper_oms_passed,
            capacity_analysis_passed,
            execution_sensitivity_passed,
            failure_analysis_passed,
        ]
        if all(all_checks):
            return "pass"
        if any(all_checks):
            return "inconclusive"
        # All checks are false — no edge to exploit.
        return "no_edge"


__all__ = [
    "CapacityAnalysis",
    "ExecutionSensitivityReport",
    "FailureAnalysis",
    "FactorPromotionGate",
    "PromotionCheckReport",
]
