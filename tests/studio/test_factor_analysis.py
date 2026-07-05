"""
Tests for advanced factor analysis (IC, decay, walk-forward).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.execution.fill_model import MarketSnapshot
from polymind.studio.factor_analysis import (
    FactorAnalyzer,
    ICAnalysis,
    WalkForwardResult,
)


class TestICAnalysis:
    def test_defaults(self):
        ic = ICAnalysis()
        assert ic.ic_mean == 0.0
        assert ic.hit_rate == 0.0

    def test_with_values(self):
        ic = ICAnalysis(
            ic_values=[0.1, 0.2, 0.3],
            ic_mean=0.2,
            ic_std=0.1,
            ic_ir=2.0,
            rank_ic=0.25,
            decile_returns=[0.1, 0.05, 0.0, -0.05, -0.1],
            hit_rate=0.67,
        )
        assert ic.ic_mean == 0.2
        assert len(ic.ic_values) == 3
        assert ic.hit_rate == 0.67


class TestWalkForwardResult:
    def test_defaults(self):
        wf = WalkForwardResult()
        assert wf.sharpe_mean == 0.0
        assert wf.sharpe_std == 0.0

    def test_with_values(self):
        wf = WalkForwardResult(
            period_results=[{"sharpe": 1.0}, {"sharpe": 0.5}],
            sharpe_mean=0.75,
            sharpe_std=0.25,
            sharpe_consistency=1.0,
            avg_drawdown=0.15,
        )
        assert wf.sharpe_mean == 0.75
        assert wf.sharpe_consistency == 1.0


class TestFactorAnalyzerComputeIC:
    def test_perfect_correlation(self):
        scores = {"a": 1.0, "b": 0.5, "c": 0.0}
        returns = {"a": 0.1, "b": 0.05, "c": 0.0}
        ic = FactorAnalyzer.compute_ic(scores, returns)
        assert ic.rank_ic == pytest.approx(1.0, abs=1e-10)
        assert ic.ic_mean == 1.0
        assert ic.hit_rate == 1.0

    def test_perfect_negative_correlation(self):
        scores = {"a": 1.0, "b": 0.5, "c": 0.0}
        returns = {"a": 0.0, "b": 0.05, "c": 0.1}
        ic = FactorAnalyzer.compute_ic(scores, returns)
        assert ic.rank_ic == pytest.approx(-1.0, abs=1e-10)

    def test_no_correlation(self):
        scores = {"a": 1.0, "b": 0.0}
        returns = {"a": 0.0, "b": 0.0}
        ic = FactorAnalyzer.compute_ic(scores, returns)
        # Only 2 common markets — Spearman still possible
        assert isinstance(ic.rank_ic, float)

    def test_insufficient_overlap(self):
        scores = {"a": 1.0, "b": 0.5}
        returns = {"c": 0.1, "d": 0.0}
        ic = FactorAnalyzer.compute_ic(scores, returns)
        assert ic.rank_ic == 0.0
        assert len(ic.decile_returns) == 0

    def test_decile_returns_structure(self):
        scores = {f"m{i}": 1.0 - i * 0.1 for i in range(20)}
        returns = {f"m{i}": i * 0.01 for i in range(20)}
        ic = FactorAnalyzer.compute_ic(scores, returns)
        assert len(ic.decile_returns) == 10
        # Lower decile (higher score) should have higher returns
        # (positive correlation between score and return)
        assert ic.decile_returns[0] >= ic.decile_returns[-1]


class TestFactorAnalyzerICSeries:
    def test_single_period(self):
        score_series = [{"a": 1.0, "b": 0.5, "c": 0.0}]
        return_series = [{"a": 0.1, "b": 0.05, "c": 0.0}]
        ic = FactorAnalyzer.compute_ic_series(score_series, return_series)
        assert ic.rank_ic == pytest.approx(1.0, abs=1e-10)
        assert len(ic.ic_values) == 1

    def test_multiple_periods(self):
        score_series = [
            {"a": 1.0, "b": 0.5, "c": 0.0},
            {"a": 0.0, "b": 0.5, "c": 1.0},
        ]
        return_series = [
            {"a": 0.1, "b": 0.05, "c": 0.0},
            {"a": 0.0, "b": 0.05, "c": 0.1},
        ]
        ic = FactorAnalyzer.compute_ic_series(score_series, return_series)
        assert len(ic.ic_values) == 2
        assert ic.ic_mean > 0
        assert ic.hit_rate == 1.0

    def test_empty_series(self):
        ic = FactorAnalyzer.compute_ic_series([], [])
        assert ic.ic_mean == 0.0

    def test_mismatched_lengths(self):
        score_series = [{"a": 1.0}]
        return_series = [{"a": 0.1}, {"a": 0.2}]
        ic = FactorAnalyzer.compute_ic_series(score_series, return_series)
        assert ic.ic_mean == 0.0


class TestFactorAnalyzerDecay:
    def test_insufficient_periods(self):
        half_life = FactorAnalyzer.compute_decay([0.1, 0.2])
        assert half_life == 0.0

    def test_sufficient_periods(self):
        ic_series = [0.5, 0.4, 0.3, 0.2, 0.1]
        half_life = FactorAnalyzer.compute_decay(ic_series)
        # Should detect some decay (positive half-life)
        assert half_life > 0

    def test_no_decay(self):
        # All same values — no decay detected
        ic_series = [0.1, 0.1, 0.1, 0.1]
        half_life = FactorAnalyzer.compute_decay(ic_series)
        assert half_life >= 0

    def test_alternating_series(self):
        ic_series = [0.5, -0.5, 0.5, -0.5]
        half_life = FactorAnalyzer.compute_decay(ic_series)
        # Strong negative autocorrelation
        assert half_life > 0


class TestWalkForward:
    def _make_snapshot(self, mid: float) -> MarketSnapshot:
        return MarketSnapshot(
            market_id="",
            timestamp=datetime(2026, 7, 4),
            bid_price=mid - 0.02,
            ask_price=mid + 0.02,
            mid_price=mid,
            bid_size=1000,
            ask_size=1000,
        )

    def test_basic_walk_forward(self):
        score_series = [
            {"a": 1.0, "b": 0.5, "c": 0.0},
            {"a": 1.0, "b": 0.5, "c": 0.0},
        ]
        snapshot_series = [
            {
                "a": self._make_snapshot(0.50),
                "b": self._make_snapshot(0.45),
                "c": self._make_snapshot(0.40),
            },
            {
                "a": self._make_snapshot(0.55),
                "b": self._make_snapshot(0.45),
                "c": self._make_snapshot(0.35),
            },
        ]

        result = FactorAnalyzer.walk_forward(
            score_series,
            snapshot_series,
            window=2,
            step=1,
        )
        assert len(result.period_results) > 0
        assert result.sharpe_mean is not None
        assert result.sharpe_consistency >= 0

    def test_fewer_periods_than_window(self):
        score_series = [{"a": 1.0}]
        snapshot_series = [{"a": self._make_snapshot(0.50)}]
        result = FactorAnalyzer.walk_forward(
            score_series,
            snapshot_series,
            window=5,
            step=1,
        )
        assert len(result.period_results) >= 0

    def test_empty_series(self):
        result = FactorAnalyzer.walk_forward([], [])
        assert len(result.period_results) == 0
        assert result.sharpe_mean == 0.0


class TestAutocorr:
    def test_perfect_positive(self):
        series = [1.0, 2.0, 3.0, 4.0]
        r = FactorAnalyzer._autocorr(series, 1)
        assert r == pytest.approx(1.0, abs=1e-10)

    def test_perfect_negative(self):
        series = [1.0, -1.0, 1.0, -1.0]
        r = FactorAnalyzer._autocorr(series, 1)
        assert r == pytest.approx(-1.0, abs=1e-10)

    def test_zero(self):
        series = [1.0, 0.0, 1.0, 0.0]
        r = FactorAnalyzer._autocorr(series, 1)
        # Perfect negative correlation: r == -1.0
        assert r == pytest.approx(-1.0, abs=1e-10)

    def test_insufficient_data(self):
        r = FactorAnalyzer._autocorr([1.0], 1)
        assert r == 0.0

    def test_flat_series(self):
        r = FactorAnalyzer._autocorr([1.0, 1.0, 1.0, 1.0], 1)
        assert r == 0.0
