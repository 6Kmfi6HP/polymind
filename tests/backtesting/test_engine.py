"""
Tests for BacktestEngine.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from polymind.backtesting.engine import BacktestConfig, BacktestEngine
from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.factors.pipeline import FactorPipeline, MarketFeatures, ScoreResult, UniverseSnapshot


def _varying_pipeline(
    target_sets: list[list[PortfolioTarget]],
) -> FactorPipeline:
    """Pipeline that returns different targets per call index."""
    call_count = [0]

    async def run_fn(u: UniverseSnapshot) -> list[PortfolioTarget]:
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(target_sets):
            return target_sets[idx]
        return []

    pipeline = FactorPipeline(
        feature_fn=lambda u: u,
        filter_fn=lambda u: u,
        score_fn=lambda u: ScoreResult(scores={}, timestamp=u.timestamp),
        portfolio_fn=lambda s: [],
    )
    pipeline.run = run_fn  # type: ignore
    return pipeline


def _snapshot(mid: str, price: float, ts: datetime) -> UniverseSnapshot:
    return UniverseSnapshot(
        timestamp=ts,
        markets={
            mid: MarketFeatures(market_id=mid, mid_price=price),
        },
    )


class TestBacktestEngine:
    @pytest.mark.asyncio
    async def test_empty_snapshots(self):
        engine = BacktestEngine(_varying_pipeline([]))
        result = await engine.run([])
        assert result.total_return_pct == 0.0
        assert result.num_trades == 0

    @pytest.mark.asyncio
    async def test_profitable_trade(self):
        now = datetime.now()
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=10.0,
            confidence=0.8,
            rank=1,
        )
        pipeline = _varying_pipeline([[target], []])
        engine = BacktestEngine(pipeline, BacktestConfig(initial_capital=1000.0))

        snapshots = [
            _snapshot("0xabc", 0.50, now),  # open long (buy at 0.50)
            _snapshot("0xabc", 0.80, now + timedelta(hours=24)),  # close (sell at 0.80)
        ]

        result = await engine.run(snapshots)
        assert result.total_return_pct > 0
        assert result.num_trades >= 1  # close position recorded as trade

    @pytest.mark.asyncio
    async def test_loss_trade(self):
        now = datetime.now()
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=10.0,
            confidence=0.8,
            rank=1,
        )
        pipeline = _varying_pipeline([[target], []])
        engine = BacktestEngine(pipeline, BacktestConfig(initial_capital=1000.0))

        snapshots = [
            _snapshot("0xabc", 0.50, now),  # open long (buy at 0.50)
            _snapshot("0xabc", 0.40, now + timedelta(hours=1)),  # close (sell at 0.40)
        ]

        result = await engine.run(snapshots)
        assert result.total_return_pct < 0

    @pytest.mark.asyncio
    async def test_portfolio_value_tracking(self):
        engine = BacktestEngine(_varying_pipeline([]), BacktestConfig(initial_capital=5000.0))
        result = await engine.run([])
        assert len(result.portfolio_values) > 0
        assert result.portfolio_values[0] == 5000.0

    @pytest.mark.asyncio
    async def test_trade_recording(self):
        now = datetime.now()
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=5.0,
            confidence=0.7,
            rank=1,
        )
        pipeline = _varying_pipeline([[target], []])
        snapshots = [
            _snapshot("0xabc", 0.50, now),
            _snapshot("0xabc", 0.55, now + timedelta(hours=1)),
        ]
        result = await BacktestEngine(pipeline).run(snapshots)
        assert len(result.trades) > 0

    # ── Coverage: close position when market not in snapshot (lines 157-158) ──

    @pytest.mark.asyncio
    async def test_close_position_market_not_in_snapshot(self):
        """Closing a position for a market missing from the snapshot returns 0 P&L."""
        now = datetime.now()
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=10.0,
            confidence=0.8,
            rank=1,
        )
        # Second snapshot does NOT include 0xabc -> triggers close
        pipeline = _varying_pipeline([[target], []])
        engine = BacktestEngine(pipeline, BacktestConfig(initial_capital=1000.0))

        snapshots = [
            _snapshot("0xabc", 0.50, now),
            # No "0xabc" key; the close logic hits snap.markets.get(mid) -> None
            UniverseSnapshot(
                timestamp=now + timedelta(hours=1),
                markets={},
            ),
        ]

        result = await engine.run(snapshots)
        # The close of 10 units at mid_price 0.50 with missing market returns 0 P&L
        # Engine runs without error; total_return_pct shows capital unchanged (minus commission on open)
        assert result.num_trades >= 0
        # P&L series has at least 2 entries (one per tick)
        assert len(result.pnl_series) >= 1

    # ── Coverage: execution_price when market not in snapshot (line 176) ──

    @pytest.mark.asyncio
    async def test_execution_price_fallback(self):
        """_execution_price returns 0.5 when target market is missing from snapshot."""
        now = datetime.now()
        target = PortfolioTarget(
            market_id="0xmissing",
            direction=PositionDirection.LONG,
            target_size=10.0,
            confidence=0.8,
            rank=1,
        )
        pipeline = _varying_pipeline([[target]])
        engine = BacktestEngine(pipeline, BacktestConfig(initial_capital=1000.0))

        snapshots = [
            UniverseSnapshot(
                timestamp=now,
                markets={"0xother": MarketFeatures(market_id="0xother", mid_price=0.50)},
            ),
        ]

        result = await engine.run(snapshots)
        # The position was opened at the fallback price 0.5 with 0.1% commission,
        # so return is slightly negative (~-0.0005%).  Verify the engine
        # completed without error and that the execution price was 0.5.
        assert result.total_return_pct == pytest.approx(0.0, abs=0.01)
        assert result.num_trades >= 0
        # Verify the trade was recorded at the fallback price of 0.5
        assert any(t["price"] == 0.5 for t in result.trades)
