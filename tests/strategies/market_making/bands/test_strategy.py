"""
Tests for BandsStrategy.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.intents import OrderSide, StrategyIntent
from polymind.execution.fill_model import MarketSnapshot
from polymind.strategies.market_making.bands.pricing import BandConfig, BandPricingConfig
from polymind.strategies.market_making.bands.strategy import BandsStrategy


class TestBandsStrategy:
    @pytest.mark.asyncio
    async def test_analyze_returns_intent(self):
        strategy = BandsStrategy()
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
    async def test_cancel_before_place(self):
        """Should cancel all existing before placing new bands."""
        strategy = BandsStrategy()
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
        assert len(intent.cancels) == 1
        assert len(intent.orders) >= 2

    @pytest.mark.asyncio
    async def test_buy_sell_balanced(self):
        strategy = BandsStrategy()
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
        strategy = BandsStrategy()
        assert strategy.name == "BandsStrategy"

    @pytest.mark.asyncio
    async def test_custom_config(self):
        bands = [BandConfig(spread_pct=0.01), BandConfig(spread_pct=0.05)]
        pricing_cfg = BandPricingConfig(bands=bands)
        strategy = BandsStrategy(pricing_config=pricing_cfg)
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
        assert len(intent.orders) == 4  # 2 bands × 2 sides

    @pytest.mark.asyncio
    async def test_market_id_in_orders(self):
        strategy = BandsStrategy()
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
        strategy = BandsStrategy()
        assert await strategy.risk_check() is True
