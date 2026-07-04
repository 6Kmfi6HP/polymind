"""
Integration: Full pipeline — Strategy → TradingEngine → PaperExecutor.

Verifies that a real strategy, real PaperExecutor, and real TradingEngine
wire together correctly for an end-to-end observe-decide-act tick.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.engine import TradingEngine
from polymind.execution.executor import PaperExecutor
from polymind.execution.fill_model import FillMode, FillModel, FillModelConfig, MarketSnapshot
from polymind.strategies import get_strategy, register_builtin_strategies


@pytest.fixture(autouse=True)
def _ensure_strategies() -> None:
    register_builtin_strategies()


@pytest.fixture
def executor() -> PaperExecutor:
    fill_model = FillModel(FillModelConfig(mode=FillMode.TAKER))
    return PaperExecutor(fill_model=fill_model, initial_cash=1_000.0)


@pytest.fixture
def market() -> MarketSnapshot:
    return MarketSnapshot(
        market_id="mkt1",
        timestamp=datetime(2026, 7, 4, 12, 0, 0),
        bid_price=0.45,
        ask_price=0.55,
        mid_price=0.50,
        bid_size=10_000.0,
        ask_size=10_000.0,
    )


class TestFullPipeline:
    async def test_full_pipeline_amm(self, executor: PaperExecutor, market: MarketSnapshot):
        """AMM strategy → TradingEngine → PaperExecutor produces orders."""
        strategy = get_strategy("amm")
        engine = TradingEngine(strategy=strategy, executor=executor)

        result = await engine.run_tick(market)

        assert result.orders_proposed > 0, "AMM should propose orders"
        assert result.risk_approved is True
        assert result.error == ""
        assert len(executor.orders) > 0

    async def test_full_pipeline_bands(self, executor: PaperExecutor, market: MarketSnapshot):
        """Bands strategy → TradingEngine → PaperExecutor."""
        strategy = get_strategy("bands")
        engine = TradingEngine(strategy=strategy, executor=executor)

        result = await engine.run_tick(market)

        assert result.orders_proposed > 0
        assert result.error == ""

    async def test_full_pipeline_classic_mm(self, executor: PaperExecutor, market: MarketSnapshot):
        """Classic MM strategy → TradingEngine → PaperExecutor."""
        strategy = get_strategy("classic_mm")
        engine = TradingEngine(strategy=strategy, executor=executor)

        result = await engine.run_tick(market)

        assert result.orders_proposed > 0
