"""Integration tests: PaperExecutor + FillModel + Risk end-to-end."""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.intents import OrderIntent, OrderSide, StrategyIntent
from polymind.execution.executor import PaperExecutor
from polymind.execution.fill_model import FillModel, FillModelConfig, FillMode, MarketSnapshot
from polymind.execution.order_identity import OrderIdentity


class TestPaperExecutor:
    @pytest.mark.asyncio
    async def test_execute_returns_dict(self, paper_executor: PaperExecutor) -> None:
        intent = StrategyIntent(timestamp=datetime(2026, 1, 1), strategy_name="test",
            orders=[OrderIntent(market_id="0xabc", side=OrderSide.BUY, price=0.51, size=100.0)])
        result = await paper_executor.execute(intent)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_dry_run(self, paper_executor: PaperExecutor) -> None:
        intent = StrategyIntent(timestamp=datetime(2026, 1, 1), strategy_name="test",
            orders=[OrderIntent(market_id="0xabc", side=OrderSide.BUY, price=0.50, size=100.0)])
        result = await paper_executor.dry_run(intent)
        assert result["dry_run"]

    @pytest.mark.asyncio
    async def test_order_identity(self) -> None:
        o1 = OrderIdentity(strategy_name="t", market_id="0xabc", side=OrderSide.BUY, price=0.5, outcome=None, client_id="c1")
        o2 = OrderIdentity(strategy_name="t", market_id="0xabc", side=OrderSide.BUY, price=0.5, outcome=None, client_id="c1")
        assert o1 == o2


class TestFillModel:
    @pytest.mark.asyncio
    async def test_taker_fills(self, market_snapshot: MarketSnapshot) -> None:
        model = FillModel(FillModelConfig(mode=FillMode.TAKER))
        result = await model.simulate(OrderIntent(market_id="0xabc", side=OrderSide.BUY, price=0.51, size=100.0), market_snapshot)
        assert result.filled

    @pytest.mark.asyncio
    async def test_passive_no_fill(self, market_snapshot: MarketSnapshot) -> None:
        model = FillModel(FillModelConfig(mode=FillMode.PASSIVE))
        result = await model.simulate(OrderIntent(market_id="0xabc", side=OrderSide.BUY, price=0.40, size=100.0), market_snapshot)
        assert not result.filled


class TestRiskLimits:
    def test_position_limit(self, limits_manager: LimitsManager) -> None:
        assert limits_manager.check_position_size("0xabc", 100.0)
        assert not limits_manager.check_position_size("0xabc", 99999.0)

    def test_order_rate(self, limits_manager: LimitsManager) -> None:
        assert limits_manager.check_order_rate(50)


class TestDrawdown:
    def test_basic_drawdown(self) -> None:
        from polymind.risk.drawdown import DrawdownTracker, DrawdownConfig
        t = DrawdownTracker(DrawdownConfig(), initial_peak=100.0)
        s = t.update(80.0)
        from polymind.risk.drawdown import DrawdownState
        assert s == DrawdownState.STOPPED
