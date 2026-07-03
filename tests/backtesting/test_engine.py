"""
Tests for BacktestEngine.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import pytest

from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.factors.pipeline import FactorPipeline, MarketFeatures, ScoreResult, UniverseSnapshot
from polymind.backtesting.engine import BacktestConfig, BacktestEngine


def _varying_pipeline(
    target_sets: List[List[PortfolioTarget]],
) -> FactorPipeline:
    """Pipeline that returns different targets per call index."""
    call_count = [0]

    async def run_fn(u: UniverseSnapshot) -> List[PortfolioTarget]:
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
            _snapshot("0xabc", 0.50, now),       # open long (buy at 0.50)
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
            _snapshot("0xabc", 0.50, now),       # open long (buy at 0.50)
            _snapshot("0xabc", 0.40, now + timedelta(hours=1)),  # close (sell at 0.40)
        ]

        result = await engine.run(snapshots)
        assert result.total_return_pct < 0

    @pytest.mark.asyncio
    async def test_portfolio_value_tracking(self):
        engine = BacktestEngine(
            _varying_pipeline([]), BacktestConfig(initial_capital=5000.0)
        )
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
