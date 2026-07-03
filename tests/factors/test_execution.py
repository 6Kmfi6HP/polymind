"""Tests for FactorExecutionBridge."""

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
    return MarketSnapshot(
        market_id="0xabc",
        bid_price=0.50,
        bid_size=1000.0,
        ask_price=0.51,
        ask_size=1000.0,
        mid_price=0.505,
        timestamp=datetime(2026, 1, 1),
    )


class TestExecutionBridgeConfig:
    def test_defaults(self) -> None:
        cfg = ExecutionBridgeConfig()
        assert cfg.default_slippage_bps == 5.0
        assert cfg.max_position_size == 1000.0
        assert cfg.min_size == 1.0


class TestFactorExecutionBridge:
    @pytest.mark.asyncio
    async def test_long_creates_buy_order(
        self, bridge: FactorExecutionBridge, snapshot: MarketSnapshot
    ) -> None:
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=100.0,
            confidence=0.8,
            rank=1,
        )
        orders = await bridge.to_order_intents(target, snapshot)
        assert len(orders) == 1
        assert orders[0].side.value == "BUY"
        assert orders[0].size == 100.0

    @pytest.mark.asyncio
    async def test_short_creates_sell_order(
        self, bridge: FactorExecutionBridge, snapshot: MarketSnapshot
    ) -> None:
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.SHORT,
            target_size=50.0,
            confidence=0.6,
            rank=3,
        )
        orders = await bridge.to_order_intents(target, snapshot)
        assert len(orders) == 1
        assert orders[0].side.value == "SELL"

    @pytest.mark.asyncio
    async def test_neutral_gives_no_orders(
        self, bridge: FactorExecutionBridge, snapshot: MarketSnapshot
    ) -> None:
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.NEUTRAL,
            target_size=100.0,
            confidence=0.0,
            rank=5,
        )
        orders = await bridge.to_order_intents(target, snapshot)
        assert orders == []

    @pytest.mark.asyncio
    async def test_size_capped_by_max_position(
        self, bridge: FactorExecutionBridge, snapshot: MarketSnapshot
    ) -> None:
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=9999.0,
            confidence=0.9,
            rank=1,
        )
        orders = await bridge.to_order_intents(target, snapshot)
        assert orders[0].size == 1000.0

    @pytest.mark.asyncio
    async def test_size_limited_by_cash(
        self, bridge: FactorExecutionBridge, snapshot: MarketSnapshot
    ) -> None:
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=1000.0,
            confidence=0.7,
            rank=2,
        )
        orders = await bridge.to_order_intents(target, snapshot, available_cash=50.0)
        assert orders[0].size == pytest.approx(99.01, rel=0.01)

    @pytest.mark.asyncio
    async def test_size_below_min_returns_empty(
        self, bridge: FactorExecutionBridge, snapshot: MarketSnapshot
    ) -> None:
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=0.1,
            confidence=0.5,
            rank=5,
        )
        orders = await bridge.to_order_intents(target, snapshot)
        assert orders == []

    @pytest.mark.asyncio
    async def test_to_cancel_intents(self, bridge: FactorExecutionBridge) -> None:
        cancels = await bridge.to_cancel_intents(["0xabc", "0xdef"])
        assert len(cancels) == 2

    @pytest.mark.asyncio
    async def test_order_has_metadata(
        self, bridge: FactorExecutionBridge, snapshot: MarketSnapshot
    ) -> None:
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=100.0,
            confidence=0.95,
            rank=1,
            reason="momentum-7d",
        )
        orders = await bridge.to_order_intents(target, snapshot)
        assert orders[0].metadata["strategy"] == "momentum-7d"
