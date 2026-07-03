"""
Tests for AMMStrategy.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.intents import OrderSide, StrategyIntent
from polymind.execution.fill_model import MarketSnapshot
from polymind.strategies.market_making.amm.pricing import AMMPricingConfig
from polymind.strategies.market_making.amm.sizing import AMMSizingConfig
from polymind.strategies.market_making.amm.strategy import AMMStrategy


class TestAMMStrategy:
    @pytest.mark.asyncio
    async def test_analyze_returns_intent(self):
        """analyze() should return a StrategyIntent with orders."""
        strategy = AMMStrategy()
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.48,
            bid_size=100.0,
            ask_price=0.52,
            ask_size=100.0,
            mid_price=0.50,
            timestamp=datetime.now(),
        )
        intent = await strategy.analyze(snap)
        assert intent is not None
        assert isinstance(intent, StrategyIntent)
        assert len(intent.orders) > 0

    @pytest.mark.asyncio
    async def test_ladder_orders_alternate(self):
        """Orders should alternate: cancel all, then place everything."""
        strategy = AMMStrategy()
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.48,
            bid_size=100.0,
            ask_price=0.52,
            ask_size=100.0,
            mid_price=0.50,
            timestamp=datetime.now(),
        )
        intent = await strategy.analyze(snap)
        # Should have cancels for market and orders for new ladder
        assert len(intent.cancels) >= 1
        assert len(intent.orders) >= 2

    @pytest.mark.asyncio
    async def test_buy_sell_balanced(self):
        """Should have same number of buys and sells."""
        strategy = AMMStrategy()
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.48,
            bid_size=100.0,
            ask_price=0.52,
            ask_size=100.0,
            mid_price=0.50,
            timestamp=datetime.now(),
        )
        intent = await strategy.analyze(snap)
        buys = sum(1 for o in intent.orders if o.side == OrderSide.BUY)
        sells = sum(1 for o in intent.orders if o.side == OrderSide.SELL)
        assert buys == sells
        assert buys > 0

    @pytest.mark.asyncio
    async def test_name_default(self):
        """Default strategy name should be AMMStrategy."""
        strategy = AMMStrategy()
        assert strategy.name == "AMMStrategy"

    @pytest.mark.asyncio
    async def test_custom_config(self):
        """Custom pricing and sizing configs should be used."""
        pricing_cfg = AMMPricingConfig(min_spread=0.05, max_spread=0.20, num_levels=3)
        sizing_cfg = AMMSizingConfig(total_exposure=50.0, concentration_pct=0.3)
        strategy = AMMStrategy(pricing_config=pricing_cfg, sizing_config=sizing_cfg)
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.48,
            bid_size=100.0,
            ask_price=0.52,
            ask_size=100.0,
            mid_price=0.50,
            timestamp=datetime.now(),
        )
        intent = await strategy.analyze(snap)
        assert len(intent.orders) == 6  # 3 buys + 3 sells

    @pytest.mark.asyncio
    async def test_market_id_in_orders(self):
        """All orders should have the correct market_id."""
        strategy = AMMStrategy()
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.48,
            bid_size=100.0,
            ask_price=0.52,
            ask_size=100.0,
            mid_price=0.50,
            timestamp=datetime.now(),
        )
        intent = await strategy.analyze(snap)
        assert all(o.market_id == "0xabc" for o in intent.orders)

    @pytest.mark.asyncio
    async def test_risk_check_default(self):
        """Default risk check should pass."""
        strategy = AMMStrategy()
        assert await strategy.risk_check() is True
