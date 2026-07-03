"""Integration tests: Factor execution bridge."""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.execution.fill_model import MarketSnapshot
from polymind.factors.execution import ExecutionBridgeConfig, FactorExecutionBridge


@pytest.fixture
def bridge() -> FactorExecutionBridge:
    return FactorExecutionBridge(ExecutionBridgeConfig())


@pytest.fixture
def snapshot() -> MarketSnapshot:
    return MarketSnapshot(market_id="0xabc", bid_price=0.50, bid_size=1000.0, ask_price=0.51, ask_size=1000.0, mid_price=0.505, timestamp=datetime(2026, 1, 1))


class TestExecutionBridge:
    @pytest.mark.asyncio
    async def test_long_to_buy(self, bridge: FactorExecutionBridge, snapshot: MarketSnapshot) -> None:
        target = PortfolioTarget(market_id="0xabc", direction=PositionDirection.LONG, target_size=100.0, confidence=0.8, rank=1)
        orders = await bridge.to_order_intents(target, snapshot)
        assert len(orders) == 1
        assert orders[0].side.value == "BUY"

    @pytest.mark.asyncio
    async def test_neutral_no_orders(self, bridge: FactorExecutionBridge, snapshot: MarketSnapshot) -> None:
        target = PortfolioTarget(market_id="0xabc", direction=PositionDirection.NEUTRAL, target_size=100.0, confidence=0.0, rank=5)
        orders = await bridge.to_order_intents(target, snapshot)
        assert orders == []

    @pytest.mark.asyncio
    async def test_cancel_intents(self, bridge: FactorExecutionBridge) -> None:
        cancels = await bridge.to_cancel_intents(["0xabc"])
        assert len(cancels) == 1
