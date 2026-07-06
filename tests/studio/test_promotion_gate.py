"""
Tests for FactorPromotionGate and related dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass

from polymind.studio.promotion_gate import (
    CapacityAnalysis,
    ExecutionSensitivityReport,
    FactorPromotionGate,
    FailureAnalysis,
    PromotionCheckReport,
)

# ── Test dataclass: CapacityAnalysis ──────────────────────────────────


class TestCapacityAnalysis:
    def test_defaults(self):
        ca = CapacityAnalysis()
        assert ca.max_capital_usd == 0.0
        assert ca.avg_daily_volume_usd == 0.0
        assert ca.market_impact_bps == 0.0
        assert ca.capacity_rating == "unknown"

    def test_construction(self):
        ca = CapacityAnalysis(
            max_capital_usd=1_000_000.0,
            avg_daily_volume_usd=5_000_000.0,
            market_impact_bps=2.5,
            capacity_rating="high",
        )
        assert ca.max_capital_usd == 1_000_000.0
        assert ca.avg_daily_volume_usd == 5_000_000.0
        assert ca.market_impact_bps == 2.5
        assert ca.capacity_rating == "high"


# ── Test dataclass: ExecutionSensitivityReport ────────────────────────


class TestExecutionSensitivityReport:
    def test_defaults(self):
        es = ExecutionSensitivityReport()
        assert es.spread_impact_bps == 0.0
        assert es.slippage_impact_bps == 0.0
        assert es.latency_sensitivity == "unknown"
        assert es.total_execution_cost_bps == 0.0

    def test_construction(self):
        es = ExecutionSensitivityReport(
            spread_impact_bps=1.5,
            slippage_impact_bps=0.5,
            latency_sensitivity="low",
            total_execution_cost_bps=2.0,
        )
        assert es.spread_impact_bps == 1.5
        assert es.slippage_impact_bps == 0.5
        assert es.latency_sensitivity == "low"
        assert es.total_execution_cost_bps == 2.0


# ── Test dataclass: FailureAnalysis ───────────────────────────────────


class TestFailureAnalysis:
    def test_defaults(self):
        fa = FailureAnalysis()
        assert fa.failure_modes == []
        assert fa.worst_case_drawdown == 0.0
        assert fa.regime_sensitivity == "unknown"

    def test_construction(self):
        fa = FailureAnalysis(
            failure_modes=["regime_change", "liquidity_crisis"],
            worst_case_drawdown=0.45,
            regime_sensitivity="medium",
        )
        assert fa.failure_modes == ["regime_change", "liquidity_crisis"]
        assert fa.worst_case_drawdown == 0.45
        assert fa.regime_sensitivity == "medium"


# ── Test dataclass: PromotionCheckReport ──────────────────────────────


@dataclass
class FakeFactorCard:
    """Minimal factor card stub for tests."""

    name: str = ""
    sharpe: float = 0.0


@dataclass
class FakeBacktestResult:
    sharpe: float = 0.0


@dataclass
class FakeWalkForwardResult:
    sharpe_consistency: float = 0.0
    sharpe_mean: float = 0.0


class TestPromotionCheckReport:
    def test_defaults(self):
        report = PromotionCheckReport()
        assert report.factor_name == ""
        assert report.all_checks_passed is False
        assert report.passed_checks == 0
        assert report.total_checks == 7
        assert report.outcome == "inconclusive"
        assert report.details == ""

    def test_all_checks_passed_true(self):
        report = PromotionCheckReport(
            factor_name="test_factor",
            executable_price_backtest=True,
            walk_forward_passed=True,
            bootstrap_confidence_passed=True,
            paper_oms_passed=True,
            capacity_analysis_passed=True,
            execution_sensitivity_passed=True,
            failure_analysis_passed=True,
        )
        assert report.all_checks_passed is True
        assert report.passed_checks == 7
        assert "PASS" in report.summary

    def test_all_checks_passed_one_false(self):
        report = PromotionCheckReport(
            factor_name="test_factor",
            executable_price_backtest=True,
            walk_forward_passed=True,
            bootstrap_confidence_passed=True,
            paper_oms_passed=True,
            capacity_analysis_passed=True,
            execution_sensitivity_passed=True,
            failure_analysis_passed=False,
        )
        assert report.all_checks_passed is False
        assert report.passed_checks == 6

    def test_all_checks_passed_all_false(self):
        report = PromotionCheckReport(factor_name="test_factor")
        assert report.all_checks_passed is False
        assert report.passed_checks == 0

    def test_passed_checks_counting(self):
        report = PromotionCheckReport(
            factor_name="test",
            executable_price_backtest=True,
            walk_forward_passed=True,
            bootstrap_confidence_passed=False,
            paper_oms_passed=True,
            capacity_analysis_passed=False,
            execution_sensitivity_passed=False,
            failure_analysis_passed=True,
        )
        assert report.passed_checks == 4  # checks 1, 2, 4, 7

    def test_summary_format(self):
        report = PromotionCheckReport(
            factor_name="momentum_7d",
            executable_price_backtest=True,
            walk_forward_passed=True,
            bootstrap_confidence_passed=True,
            paper_oms_passed=True,
            capacity_analysis_passed=True,
            execution_sensitivity_passed=True,
            failure_analysis_passed=True,
            outcome="pass",
        )
        summary = report.summary
        assert "[PASS]" in summary
        assert "momentum_7d" in summary
        assert "7/7" in summary

    def test_summary_fail_format(self):
        report = PromotionCheckReport(
            factor_name="bad_factor",
            outcome="no_edge",
        )
        summary = report.summary
        assert "[FAIL]" in summary
        assert "bad_factor" in summary
        assert "0/7" in summary

    def test_nested_analyses(self):
        ca = CapacityAnalysis(capacity_rating="medium")
        es = ExecutionSensitivityReport(total_execution_cost_bps=3.0)
        fa = FailureAnalysis(failure_modes=["regime_change"])
        report = PromotionCheckReport(
            factor_name="test",
            capacity=ca,
            execution_sensitivity=es,
            failure_analysis=fa,
        )
        assert report.capacity is ca
        assert report.execution_sensitivity is es
        assert report.failure_analysis is fa
        assert report.capacity.capacity_rating == "medium"


# ── Test FactorPromotionGate ──────────────────────────────────────────


class TestFactorPromotionGate:
    def test_check_with_full_data(self):
        """All seven checks pass when complete, valid data is provided."""
        gate = FactorPromotionGate()
        factor_card = FakeFactorCard(name="momentum_7d")
        backtest_result = FakeBacktestResult(sharpe=1.5)
        walk_forward = FakeWalkForwardResult(sharpe_consistency=0.8, sharpe_mean=1.2)
        capacity = CapacityAnalysis(capacity_rating="high")
        sensitivity = ExecutionSensitivityReport(total_execution_cost_bps=2.0)
        failure = FailureAnalysis(failure_modes=["regime_change"])

        report = gate.check(
            factor_card=factor_card,
            backtest_result=backtest_result,
            walk_forward_result=walk_forward,
            capacity=capacity,
            execution_sensitivity=sensitivity,
            failure_analysis=failure,
            bootstrap_confidence_passed=True,
            paper_oms_passed=True,
        )

        assert report.factor_name == "momentum_7d"
        assert report.executable_price_backtest is True
        assert report.walk_forward_passed is True
        assert report.bootstrap_confidence_passed is True
        assert report.paper_oms_passed is True
        assert report.capacity_analysis_passed is True
        assert report.execution_sensitivity_passed is True
        assert report.failure_analysis_passed is True
        assert report.all_checks_passed is True
        assert report.passed_checks == 7
        assert report.outcome == "pass"

    def test_check_with_empty_data(self):
        """Only checks with explicitly provided data pass; everything else fails."""
        gate = FactorPromotionGate()
        report = gate.check()

        assert report.factor_name == "unknown"
        assert report.all_checks_passed is False
        assert report.passed_checks == 0
        assert report.executable_price_backtest is False
        assert report.walk_forward_passed is False
        assert report.bootstrap_confidence_passed is False
        assert report.paper_oms_passed is False
        assert report.capacity_analysis_passed is False
        assert report.execution_sensitivity_passed is False
        assert report.failure_analysis_passed is False

    def test_check_with_partial_data(self):
        """When only some checks have data, only those pass."""
        gate = FactorPromotionGate()
        backtest_result = FakeBacktestResult(sharpe=2.0)

        report = gate.check(
            backtest_result=backtest_result,
            bootstrap_confidence_passed=True,
        )

        assert report.executable_price_backtest is True
        assert report.bootstrap_confidence_passed is True
        assert report.walk_forward_passed is False
        assert report.paper_oms_passed is False
        assert report.capacity_analysis_passed is False
        assert report.execution_sensitivity_passed is False
        assert report.failure_analysis_passed is False
        assert report.passed_checks == 2
        assert report.all_checks_passed is False

    def test_backtest_sharpe_zero_is_not_executable(self):
        """A backtest result with sharpe == 0 should fail the check."""
        gate = FactorPromotionGate()
        backtest_result = FakeBacktestResult(sharpe=0.0)

        report = gate.check(backtest_result=backtest_result)
        assert report.executable_price_backtest is False

    def test_backtest_sharpe_negative_not_executable(self):
        """A backtest result with negative sharpe should fail the check."""
        gate = FactorPromotionGate()
        backtest_result = FakeBacktestResult(sharpe=-1.0)

        report = gate.check(backtest_result=backtest_result)
        assert report.executable_price_backtest is False

    def test_walk_forward_zero_consistency_fails(self):
        """Walk-forward with sharpe_consistency <= 0 should fail."""
        gate = FactorPromotionGate()
        wf = FakeWalkForwardResult(sharpe_consistency=0.0, sharpe_mean=1.0)

        report = gate.check(walk_forward_result=wf)
        assert report.walk_forward_passed is False

    def test_walk_forward_negative_mean_fails(self):
        """Walk-forward with sharpe_mean <= 0 should fail."""
        gate = FactorPromotionGate()
        wf = FakeWalkForwardResult(sharpe_consistency=0.8, sharpe_mean=-0.5)

        report = gate.check(walk_forward_result=wf)
        assert report.walk_forward_passed is False

    def test_capacity_rating_low_fails(self):
        """Capacity analysis fails when rating is 'low'."""
        gate = FactorPromotionGate()
        capacity = CapacityAnalysis(capacity_rating="low")

        report = gate.check(capacity=capacity)
        assert report.capacity_analysis_passed is False

    def test_capacity_rating_medium_passes(self):
        """Capacity analysis passes when rating is 'medium'."""
        gate = FactorPromotionGate()
        capacity = CapacityAnalysis(capacity_rating="medium")

        report = gate.check(capacity=capacity)
        assert report.capacity_analysis_passed is True

    def test_outcome_determination_all_pass(self):
        """When all checks pass, outcome should be 'pass'."""
        gate = FactorPromotionGate()
        report = gate.check(
            factor_card=FakeFactorCard(name="test"),
            backtest_result=FakeBacktestResult(sharpe=1.0),
            walk_forward_result=FakeWalkForwardResult(sharpe_consistency=1.0, sharpe_mean=0.5),
            capacity=CapacityAnalysis(capacity_rating="high"),
            execution_sensitivity=ExecutionSensitivityReport(),
            failure_analysis=FailureAnalysis(),
            bootstrap_confidence_passed=True,
            paper_oms_passed=True,
        )
        assert report.outcome == "pass"

    def test_outcome_no_edge_when_core_fails(self):
        """When both core analytical checks fail, outcome should be 'no_edge'."""
        gate = FactorPromotionGate()
        report = gate.check()
        assert report.outcome == "no_edge"

    def test_outcome_inconclusive_with_mixed(self):
        """When some checks pass but not all, outcome should be 'inconclusive'."""
        gate = FactorPromotionGate()
        report = gate.check(
            backtest_result=FakeBacktestResult(sharpe=1.0),
            bootstrap_confidence_passed=True,
        )
        assert report.outcome == "inconclusive"

    def test_check_with_factor_card_object(self):
        """Factor name should be extracted from a card-like object."""
        from dataclasses import field as dc_field

        gate = FactorPromotionGate()

        @dataclass
        class FakeDef:
            name: str = ""

        @dataclass
        class FactorCardStub:
            definition: FakeDef = dc_field(default_factory=lambda: FakeDef(name="momentum_factor"))

        report = gate.check(factor_card=FactorCardStub())
        assert report.factor_name == "momentum_factor"

    def test_check_with_named_object(self):
        """Factor name should be extracted from an object with a .name attr."""
        gate = FactorPromotionGate()

        @dataclass
        class NamedStub:
            name: str = ""

        report = gate.check(factor_card=NamedStub(name="volatility_factor"))
        assert report.factor_name == "volatility_factor"
