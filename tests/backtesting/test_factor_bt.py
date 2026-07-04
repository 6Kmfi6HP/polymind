"""
Unit tests for FactorBacktester with CLOB-aware execution prices.
"""

from __future__ import annotations

from datetime import datetime

from polymind.backtesting.factor_bt import (
    FactorBacktestConfig,
    FactorBacktester,
    FactorBacktestResult,
    _compute_max_drawdown,
    _compute_sharpe,
    _compute_sortino,
)
from polymind.execution.fill_model import MarketSnapshot


def _snap(
    market_id: str,
    bid: float = 0.45,
    ask: float = 0.55,
) -> MarketSnapshot:
    return MarketSnapshot(
        market_id=market_id,
        timestamp=datetime(2026, 7, 4),
        bid_price=bid,
        ask_price=ask,
        mid_price=(bid + ask) / 2,
        bid_size=1000.0,
        ask_size=1000.0,
    )


class TestFactorBacktester:
    def test_open_at_ask_close_at_bid(self):
        """FactorBacktester should open at ask_price and close at bid_price."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=2, max_position_size=500.0))

        scores = {"mkt1": 1.0, "mkt2": 0.5}
        snaps = {
            "mkt1": _snap("mkt1", bid=0.45, ask=0.55),
            "mkt2": _snap("mkt2", bid=0.40, ask=0.50),
        }
        result = bt.run(scores, snaps)

        # Should open positions at ask_price (0.55 and 0.50)
        assert result.total_trades == 2

        # Close mkt2 (lower score) — close at bid=0.40, entry was ask=0.50
        scores2 = {"mkt1": 1.0, "mkt3": 0.8}
        snaps2 = {
            "mkt1": _snap("mkt1", bid=0.46, ask=0.56),
            "mkt2": _snap("mkt2", bid=0.40, ask=0.50),  # needed to close
            "mkt3": _snap("mkt3", bid=0.60, ask=0.70),
        }
        result2 = bt.run(scores2, snaps2)

        # mkt2 closed: entry 0.50 → exit 0.40 → PnL = -0.10
        # trades: close mkt2, open mkt3
        assert result2.total_trades == 4  # cumulative
        assert result2.total_return < 0  # should have a loss from spread

    def test_empty_scores(self):
        bt = FactorBacktester(FactorBacktestConfig())
        result = bt.run({}, {})
        assert result.total_trades == 0

    def test_empty_snapshots(self):
        bt = FactorBacktester(FactorBacktestConfig())
        result = bt.run({"mkt1": 1.0}, {})
        assert result.total_trades == 0

    def test_multi_step(self):
        """Three-step backtest tracks positions across calls."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=1, max_position_size=500.0))

        # Step 1: open mkt1
        result1 = bt.run(
            {"mkt1": 1.0, "mkt2": 0.5},
            {
                "mkt1": _snap("mkt1", bid=0.45, ask=0.55),
                "mkt2": _snap("mkt2", bid=0.40, ask=0.50),
            },
        )
        assert result1.total_trades == 1

        # Step 2: rotate to mkt2 (close mkt1, open mkt2)
        result2 = bt.run(
            {"mkt2": 1.0, "mkt1": 0.3},
            {
                "mkt1": _snap("mkt1", bid=0.44, ask=0.54),
                "mkt2": _snap("mkt2", bid=0.42, ask=0.52),
            },
        )
        assert result2.total_trades == 3  # cumulative 1 + 2
        assert result2.total_trades == 3  # cumulative 1 + 2

        # Step 3: close mkt2 (pass empty scores, include mkt2 snapshot)
        result3 = bt.run(
            {},
            {
                "mkt2": _snap("mkt2", bid=0.43, ask=0.53),
            },
        )
        assert result3.total_trades == 4


class TestMetricHelpers:
    def test_compute_sharpe(self):
        pnl = [1.0, 1.0, 0.9, 1.1, 0.95]
        sharpe = _compute_sharpe(pnl)
        assert sharpe > 0

    def test_compute_sharpe_short_series(self):
        assert _compute_sharpe([1.0]) == 0.0

    def test_compute_sharpe_no_volatility(self):
        """Constant zero returns → zero Sharpe."""
        assert _compute_sharpe([0.0, 0.0, 0.0]) == 0.0

    def test_compute_sortino(self):
        """Sortino with negative returns should give a finite ratio."""
        pnl = [1.0, -0.5, 0.8, -1.2, 0.9]
        sortino = _compute_sortino(pnl)
        assert sortino != 0.0  # should be a finite non-zero value

    def test_compute_max_drawdown(self):
        """Drawdown should reflect the peak-to-trough drop."""
        pnl = [10.0, 5.0, -20.0, 10.0, 5.0]
        dd = _compute_max_drawdown(pnl)
        # peak at 15, trough at -5 → drawdown = 20
        assert dd == 20.0

    def test_compute_max_drawdown_positive(self):
        """All positive returns → zero drawdown."""
        assert _compute_max_drawdown([1.0, 2.0, 3.0]) == 0.0

    def test_compute_sortino_short_series(self):
        """Line 246-247: Sortino with < 2 returns → 0."""
        assert _compute_sortino([1.0]) == 0.0

    def test_compute_sortino_no_downside(self):
        """Line 250-251: Sortino with no negative returns → 0."""
        assert _compute_sortino([1.0, 2.0, 3.0]) == 0.0

    def test_compute_sortino_zero_downside_std(self):
        """Line 254-255: Sortino with zero downside std → 0."""
        assert _compute_sortino([0.0, 0.0, 0.0]) == 0.0


class TestConfigProperties:
    def test_factor_backtest_config_defaults(self):
        cfg = FactorBacktestConfig()
        assert cfg.initial_capital == 10000.0
        assert cfg.lookback_days == 30
        assert cfg.top_n == 5

    def test_result_num_winners(self):
        res = FactorBacktestResult(total_trades=10, win_rate=0.6)
        assert res.num_winners == 6
        assert res.num_losers == 4

    def test_result_num_winners_zero_trades(self):
        res = FactorBacktestResult()
        assert res.num_winners == 0


class TestBacktesterEdgeCases:
    def test_close_position_without_snapshot(self):
        """Closing positions without closing snapshot skips trades."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))
        bt._positions["mkt1"] = 0.50  # entry price as float
        result = bt.run({}, {})  # no snapshot for mkt1
        assert result.total_trades == 0
        assert "mkt1" in bt._positions  # not closed

    def test_line_135_peak_update(self):
        """Line 135: peak cumulative update in close-all path."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))
        # Open mkt1 via main flow
        r1 = bt.run({"mkt1": 1.0}, {"mkt1": _snap("mkt1", 0.45, 0.55)})
        assert r1.total_trades == 1
        # Close mkt1 with profit in close-all path (empty scores)
        r2 = bt.run({}, {"mkt1": _snap("mkt1", 0.60, 0.70)})
        assert r2.total_trades == 2
        assert r2.total_return > 0  # profit pushes peak up

    def test_reopen_closed_position(self):
        """Position closed in step 1 can be re-opened later."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))
        r1 = bt.run({"mkt1": 1.0}, {"mkt1": _snap("mkt1", 0.45, 0.55)})
        assert r1.total_trades == 1  # opened mkt1
        # Step 2: rotate to mkt2 → close mkt1, open mkt2
        r2 = bt.run(
            {"mkt2": 1.0},
            {
                "mkt1": _snap("mkt1", 0.44, 0.54),
                "mkt2": _snap("mkt2", 0.50, 0.60),
            },
        )
        assert r2.total_trades >= 2  # at least close + open
        # Step 3: rotate back to mkt1 → close mkt2, open mkt1
        r3 = bt.run(
            {"mkt1": 1.0},
            {
                "mkt2": _snap("mkt2", 0.49, 0.59),
                "mkt1": _snap("mkt1", 0.46, 0.56),
            },
        )
        assert r3.total_trades >= 4  # cumulative

    def test_new_peak_cumulative(self):
        """Line 170: peak cumulative PnL update in main flow (active scores)."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))
        # Step 1: open mkt1 at ask 0.55
        r1 = bt.run({"mkt1": 1.0}, {"mkt1": _snap("mkt1", 0.45, 0.55)})
        assert r1.total_trades == 1
        # Step 2: rotate to mkt2 — closes mkt1 at bid 0.60 = +0.05 profit
        r2 = bt.run(
            {"mkt2": 1.0},
            {
                "mkt1": _snap("mkt1", 0.60, 0.70),
                "mkt2": _snap("mkt2", 0.50, 0.60),
            },
        )
        assert r2.total_trades >= 2
        assert r2.total_return > 0  # profitable close pushes peak

    def test_selected_no_snapshot_skipped(self):
        """Line 159: selected market with no snapshot is skipped."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=2))
        # mkt1 and mkt2 selected, but only mkt1 has a snapshot
        r = bt.run({"mkt1": 1.0, "mkt2": 0.5}, {"mkt1": _snap("mkt1", 0.45, 0.55)})
        # mkt2 skipped due to no snapshot → only mkt1 opened
        assert r.total_trades == 1

    def test_max_drawdown_in_result(self):
        """Result.max_drawdown is populated after 2+ trades (line 210)."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))
        bt._positions["mkt1"] = 0.60
        bt.run({}, {"mkt1": _snap("mkt1", 0.40, 0.50)})
        bt._positions["mkt2"] = 0.50
        r2 = bt.run({}, {"mkt2": _snap("mkt2", 0.60, 0.70)})
        # pnl_hist now has 2 entries → max_dd computed
        assert r2.max_drawdown > 0

    def test_sortino_in_result(self):
        """Result.sortino is populated after enough trades."""
        bt = FactorBacktester(FactorBacktestConfig(top_n=1))
        bt._positions["mkt1"] = 0.50
        bt.run({}, {"mkt1": _snap("mkt1", 0.40, 0.50)})
        bt._positions["mkt2"] = 0.50
        r2 = bt.run({}, {"mkt2": _snap("mkt2", 0.60, 0.70)})
        # Sortino requires 2+ entries in pnl_history
        assert r2.total_trades == 2
        assert isinstance(r2.sortino, float)
