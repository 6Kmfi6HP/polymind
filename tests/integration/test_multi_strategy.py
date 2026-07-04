"""
Integration: Multi-strategy swap in TradingEngine.

Verifies every built-in strategy produces valid intents through
the full pipeline.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.engine import TradingEngine
from polymind.execution.executor import PaperExecutor
from polymind.execution.fill_model import FillMode, FillModel, FillModelConfig, MarketSnapshot
from polymind.strategies import (
    get_strategy,
    list_strategies,
    register_builtin_strategies,
)


@pytest.fixture(autouse=True)
def _ensure_strategies() -> None:
    register_builtin_strategies()


@pytest.fixture
def executor() -> PaperExecutor:
    return PaperExecutor(fill_model=FillModel(FillModelConfig(mode=FillMode.TAKER)))


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


STRATEGIES_TO_TEST = ["amm", "bands", "classic_mm"]  # maker_rebate requires outcomes dict


class TestMultiStrategy:
    async def test_each_builtin_strategy_produces_intents(
        self,
        executor: PaperExecutor,
        market: MarketSnapshot,
    ):
        for name in STRATEGIES_TO_TEST:
            strategy = get_strategy(name)
            engine = TradingEngine(strategy=strategy, executor=executor)

            result = await engine.run_tick(market)

            assert result.orders_proposed > 0, f"{name} should propose orders"
            assert result.strategy == strategy.name
            assert result.risk_approved is True
            assert result.error == ""

    async def test_strategy_count(self):
        all_strategies = list_strategies()
        assert len(all_strategies) >= 4
        for name in STRATEGIES_TO_TEST:
            assert name in all_strategies, f"{name} should be registered"
