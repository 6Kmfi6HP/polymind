"""
Tests for performance metrics.
"""

from __future__ import annotations

from polymind.backtesting.metrics import compute_metrics


class TestComputeMetrics:
    def test_empty_returns(self):
        m = compute_metrics([])
        assert m.total_return_pct == 0.0
        assert m.num_trades == 0

    def test_all_positive(self):
        m = compute_metrics([0.01, 0.02, 0.015])
        assert m.total_return_pct > 0
        assert m.win_rate == 1.0
        assert m.profit_factor == float("inf")

    def test_mixed_returns(self):
        m = compute_metrics([0.05, -0.02, 0.03, -0.01])
        assert m.num_trades == 4
        assert 0 < m.win_rate < 1.0
        assert m.profit_factor > 0

    def test_sharpe_positive(self):
        m = compute_metrics([0.001] * 252, risk_free_rate=0.0, periods_per_year=252)
        assert m.sharpe_ratio > 0

    def test_sharpe_negative(self):
        m = compute_metrics([-0.001] * 100)
        assert m.sharpe_ratio < 0

    def test_drawdown(self):
        m = compute_metrics([0.10, -0.20, 0.05])
        assert m.max_drawdown_pct > 0
