"""
Tests for factor strategy backtesting.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.backtesting.factor_bt import (
    FactorBacktestConfig,
    FactorBacktestResult,
    FactorBacktester,
    _compute_max_drawdown,
    _compute_sharpe,
    _compute_sortino,
)
from polymind.execution.fill_model import MarketSnapshot


# ======================================================================
# Helpers
# ======================================================================


def _snapshot(market_id: str, mid_price: float) -> MarketSnapshot:
    return MarketSnapshot(
        market_id=market_id,
        bid_price=mid_price - 0.01,
        bid_size=100.0,
        ask_price=mid_price + 0.01,
        ask_size=100.0,
        mid_price=mid_price,
        timestamp=datetime(2025, 1, 1),
    )


# ======================================================================
# FactorBacktestResult
# ======================================================================


class TestFactorBacktestResult:
    def test_default_construction(self) -> None:
        result = FactorBacktestResult()
        assert result.market_id == ""
        assert result.total_trades == 0
        assert result.win_rate == 0.0
        assert result.sharpe == 0.0
        assert result.sortino == 0.0
        assert result.max_drawdown == 0.0
        assert result.total_return == 0.0
        assert result.pnl_history == []

    def test_construction_with_values(self) -> None:
        result = FactorBacktestResult(
            market_id="0xabc",
            total_trades=10,
            win_rate=0.6,
            sharpe=1.5,
            sortino=2.0,
            max_drawdown=0.05,
            total_return=100.0,
            pnl_history=[10.0, -5.0, 8.0],
        )
        assert result.market_id == "0xabc"
        assert result.total_trades == 10
        assert result.win_rate == 0.6
        assert result.sharpe == 1.5
        assert result.sortino == 2.0
        assert result.max_drawdown == 0.05
        assert result.total_return == 100.0
        assert result.pnl_history == [10.0, -5.0, 8.0]

    def test_num_winners_derived(self) -> None:
        result = FactorBacktestResult(total_trades=10, win_rate=0.6)
        assert result.num_winners == 6
        assert result.num_losers == 4

    def test_num_winners_zero_trades(self) -> None:
        result = FactorBacktestResult()
        assert result.num_winners == 0
        assert result.num_losers == 0


# ======================================================================
# FactorBacktestConfig
# ======================================================================


class TestFactorBacktestConfig:
    def test_defaults(self) -> None:
        config = FactorBacktestConfig()
        assert config.initial_capital == 10000.0
        assert config.lookback_days == 30
        assert config.rebal_freq_hours == 4
        assert config.top_n == 5
        assert config.max_position_size == 1000.0

    def test_custom_values(self) -> None:
        config = FactorBacktestConfig(
            initial_capital=50000.0,
            lookback_days=60,
            rebal_freq_hours=24,
            top_n=10,
            max_position_size=5000.0,
        )
        assert config.initial_capital == 50000.0
        assert config.lookback_days == 60
        assert config.rebal_freq_hours == 24
        assert config.top_n == 10
        assert config.max_position_size == 5000.0


# ======================================================================
# FactorBacktester
# ======================================================================


class TestFactorBacktester:
    def test_init_with_config(self) -> None:
        config = FactorBacktestConfig(top_n=3)
        bt = FactorBacktester(config)
        assert bt.config == config

    def test_init_default_config(self) -> None:
        config = FactorBacktestConfig()
        bt = FactorBacktester(config)
        assert bt.config.initial_capital == 10000.0

    # ------------------------------------------------------------------
    # run() -- empty / edge cases
    # ------------------------------------------------------------------

    def test_run_empty_scores(self) -> None:
        bt = FactorBacktester(FactorBacktestConfig())
        result = bt.run({}, {"0xabc": _snapshot("0xabc", 1.0)})
        assert result.total_trades == 0
        assert result.total_return == 0.0
        assert result.sharpe == 0.0

    def test_run_empty_snapshots(self) -> None:
        bt = FactorBacktester(FactorBacktestConfig())
        result = bt.run({"0xabc": 0.9}, {})
        assert result.total_trades == 0

    def test_run_both_empty(self) -> None:
        bt = FactorBacktester(FactorBacktestConfig())
        result = bt.run({}, {})
        assert result.total_trades == 0
        assert result.market_id == ""

    # ------------------------------------------------------------------
    # run() -- single-step scenarios
    # ------------------------------------------------------------------

    def test_run_selects_top_market(self) -> None:
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))
        snapshots = {
            "m1": _snapshot("m1", 10.0),
            "m2": _snapshot("m2", 5.0),
        }
        result = bt.run({"m1": 0.9, "m2": 0.5}, snapshots)
        assert "m1" in result.market_id
        assert result.total_trades >= 1

    def test_run_top_n_markets(self) -> None:
        bt = FactorBacktester(FactorBacktestConfig(top_n=2))
        snapshots = {
            "m1": _snapshot("m1", 10.0),
            "m2": _snapshot("m2", 9.0),
            "m3": _snapshot("m3", 8.0),
        }
        result = bt.run({"m1": 0.9, "m2": 0.5, "m3": 0.1}, snapshots)
        selected = result.market_id.split(", ")
        assert len(selected) == 2
        assert "m1" in selected
        assert "m2" in selected

    # ------------------------------------------------------------------
    # run() -- multi-step: position rotation, PnL, and metrics
    # ------------------------------------------------------------------

    def test_run_opens_and_closes_positions(self) -> None:
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))

        snap1 = {"m1": _snapshot("m1", 10.0), "m2": _snapshot("m2", 5.0)}
        r1 = bt.run({"m1": 1.0, "m2": 0.0}, snap1)
        assert r1.total_trades == 1
        assert r1.market_id == "m1"

        snap2 = {"m1": _snapshot("m1", 12.0), "m2": _snapshot("m2", 6.0)}
        r2 = bt.run({"m1": 0.0, "m2": 1.0}, snap2)
        assert r2.total_trades == 3
        assert r2.total_return == 2.0

    def test_run_pnl_accumulates(self) -> None:
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))

        snap1 = {"m1": _snapshot("m1", 10.0)}
        bt.run({"m1": 1.0}, snap1)

        snap2 = {"m1": _snapshot("m1", 15.0), "m2": _snapshot("m2", 1.0)}
        r2 = bt.run({"m2": 1.0, "m1": 0.0}, snap2)
        assert r2.total_return == 5.0
        assert len(r2.pnl_history) == 2
        assert r2.pnl_history == [0.0, 5.0]

    def test_run_loss_pnl(self) -> None:
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))

        snap1 = {"m1": _snapshot("m1", 10.0)}
        bt.run({"m1": 1.0}, snap1)

        snap2 = {"m1": _snapshot("m1", 7.0), "m2": _snapshot("m2", 1.0)}
        r2 = bt.run({"m2": 1.0, "m1": 0.0}, snap2)
        assert r2.total_return == -3.0
        assert r2.win_rate == 0.0

    # ------------------------------------------------------------------
    # run() -- metrics
    # ------------------------------------------------------------------

    def test_run_sharpe_only_one_step(self) -> None:
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))
        snap = {"m1": _snapshot("m1", 10.0)}
        r = bt.run({"m1": 1.0}, snap)
        assert r.sharpe == 0.0

    def test_run_sharpe_multiple_steps(self) -> None:
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))

        snap1 = {"m1": _snapshot("m1", 10.0)}
        bt.run({"m1": 1.0}, snap1)

        snap2 = {"m1": _snapshot("m1", 15.0), "m2": _snapshot("m2", 1.0)}
        bt.run({"m2": 1.0, "m1": 0.0}, snap2)

        snap3 = {"m2": _snapshot("m2", 2.0), "m3": _snapshot("m3", 1.0)}
        r3 = bt.run({"m3": 1.0, "m2": 0.0}, snap3)

        assert r3.sharpe != 0.0

    # ------------------------------------------------------------------
    # run() -- state reset / fresh instance isolation
    # ------------------------------------------------------------------

    def test_fresh_instance_no_state_leak(self) -> None:
        bt1 = FactorBacktester(FactorBacktestConfig(top_n=1))
        snap = {"m1": _snapshot("m1", 10.0)}
        r1 = bt1.run({"m1": 1.0}, snap)
        assert r1.total_trades == 1

        bt2 = FactorBacktester(FactorBacktestConfig(top_n=1))
        r2 = bt2.run({"m1": 1.0}, snap)
        assert r2.total_trades == 1


# ======================================================================
# Metric helpers
# ======================================================================


class TestComputeSharpe:
    def test_empty(self) -> None:
        assert _compute_sharpe([]) == 0.0

    def test_single(self) -> None:
        assert _compute_sharpe([1.0]) == 0.0

    def test_positive_series(self) -> None:
        s = _compute_sharpe([1.0, 2.0, 1.5])
        assert s > 0.0

    def test_zero_variance(self) -> None:
        assert _compute_sharpe([1.0, 1.0, 1.0]) == 0.0


class TestComputeSortino:
    def test_empty(self) -> None:
        assert _compute_sortino([]) == 0.0

    def test_no_downside(self) -> None:
        assert _compute_sortino([1.0, 2.0]) == 0.0

    def test_with_downside(self) -> None:
        s = _compute_sortino([1.0, -0.5, 0.5])
        assert s != 0.0


class TestComputeMaxDrawdown:
    def test_empty(self) -> None:
        assert _compute_max_drawdown([]) == 0.0

    def test_rising(self) -> None:
        assert _compute_max_drawdown([1.0, 2.0, 3.0]) == 0.0

    def test_with_drawdown(self) -> None:
        dd = _compute_max_drawdown([10.0, -5.0, 2.0])
        assert dd == 5.0

    def test_peak_after_trough(self) -> None:
        dd = _compute_max_drawdown([5.0, -3.0, 10.0])
        assert dd == 3.0
