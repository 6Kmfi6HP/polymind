"""
Advanced tests for FillModel enhancements: partial fill, queue position, expiry.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.core.intents import OrderIntent, OrderSide
from polymind.execution.fill_model import FillMode, FillModel, FillModelConfig, FillResult, MarketSnapshot


class TestFillModelPartialFill:
    @pytest.mark.asyncio
    async def test_partial_fill_reduces_size(self):
        """Partial fill should fill only a portion and update remaining_size."""
        cfg = FillModelConfig(
            mode=FillMode.TAKER,
            taker_fee_rate=0.003,
        )
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.85,
            size=100.0,
        )
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=50.0,  # only 50 available at ask
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        result = await model.simulate(intent, snap)
        # Since the ask_size limits fill, the fill should be partial
        assert result.filled is True
        assert result.fill_size == 50.0
        assert result.remaining_size == 50.0

    @pytest.mark.asyncio
    async def test_full_fill_when_size_available(self):
        """When enough size is available, full fill."""
        cfg = FillModelConfig(mode=FillMode.TAKER)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.85,
            size=50.0,
        )
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        result = await model.simulate(intent, snap)
        assert result.filled is True
        assert result.fill_size == 50.0
        assert result.remaining_size == 0.0

    @pytest.mark.asyncio
    async def test_sell_partial_fill_limited_by_bid_size(self):
        """Sell should be limited by bid_size."""
        cfg = FillModelConfig(mode=FillMode.TAKER)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.SELL,
            price=0.80,
            size=200.0,
        )
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=50.0,  # only 50 available at bid
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        result = await model.simulate(intent, snap)
        assert result.filled is True
        assert result.fill_size == 50.0
        assert result.remaining_size == 150.0


class TestFillModelQueuePosition:
    """Test that FillModel correctly estimates queue position delays."""

    @pytest.mark.asyncio
    async def test_queue_position_delays_fill(self):
        """With deep queue position (1.0 = 0% fill prob), passive fill is delayed."""
        cfg = FillModelConfig(mode=FillMode.PASSIVE, queue_position_pct=1.0)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.86,  # above ask, so in theory would cross
            size=10.0,
        )
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        result = await model.simulate(intent, snap)
        # queue_position_pct=1.0 means fill_probability=0 → always delayed
        assert result.filled is False

    @pytest.mark.asyncio
    async def test_shallow_queue_allows_fill(self):
        """With shallow queue position, passive buy at/above ask should fill."""
        cfg = FillModelConfig(mode=FillMode.PASSIVE, queue_position_pct=0.1)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.86,  # above ask
            size=10.0,
        )
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        result = await model.simulate(intent, snap)
        assert result.filled is True


class TestFillModelExpiry:
    @pytest.mark.asyncio
    async def test_expired_order_not_filled(self):
        """An order past its expiration should not be filled."""
        cfg = FillModelConfig(mode=FillMode.TAKER)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            expiration=datetime(2020, 1, 1, tzinfo=timezone.utc),  # long expired
        )
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        result = await model.simulate(intent, snap)
        assert result.filled is False
        assert result.remaining_size == 10.0

    @pytest.mark.asyncio
    async def test_non_expired_order_fills_normally(self):
        """An order within its expiration should fill normally."""
        cfg = FillModelConfig(mode=FillMode.TAKER)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            expiration=datetime(2030, 1, 1, tzinfo=timezone.utc),  # far future
        )
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        result = await model.simulate(intent, snap)
        assert result.filled is True
