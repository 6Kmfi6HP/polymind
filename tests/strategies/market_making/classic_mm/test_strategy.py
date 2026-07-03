"""
Tests for ClassicMMStrategy.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.intents import OrderSide, StrategyIntent
from polymind.execution.fill_model import MarketSnapshot
from polymind.strategies.market_making.classic_mm.strategy import ClassicMMStrategy


class TestClassicMMStrategy:
    @pytest.mark.asyncio
    async def test_analyze_returns_intent(self):
        strategy = ClassicMMStrategy()
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
    async def test_sell_only(self):
        """Classic MM should only place sell orders (split → sell remainder)."""
        strategy = ClassicMMStrategy()
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
        assert all(o.side == OrderSide.SELL for o in intent.orders)

    @pytest.mark.asyncio
    async def test_places_limit_orders(self):
        """Orders should be limit (GTC) sell orders."""
        strategy = ClassicMMStrategy()
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
        for o in intent.orders:
            assert o.price > 0
            assert o.size > 0

    @pytest.mark.asyncio
    async def test_cancel_before_place(self):
        """Should cancel existing before placing new orders."""
        strategy = ClassicMMStrategy()
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

    @pytest.mark.asyncio
    async def test_price_above_bid(self):
        """Sell price should be above or near bid."""
        strategy = ClassicMMStrategy()
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
        for o in intent.orders:
            assert o.price >= snap.bid_price

    @pytest.mark.asyncio
    async def test_market_id(self):
        strategy = ClassicMMStrategy()
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
