"""
Tests for FillModel, FillModelConfig, FillResult, FillMode, and MarketSnapshot.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.intents import OrderIntent, OrderSide
from polymind.execution.fill_model import (
    FillMode,
    FillModel,
    FillModelConfig,
    FillResult,
    MarketSnapshot,
)


class TestFillMode:
    def test_enum_values_distinct(self):
        assert FillMode.PASSIVE != FillMode.TAKER


class TestMarketSnapshot:
    def test_construction(self):
        now = datetime.now()
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=now,
        )
        assert snap.market_id == "0xabc"
        assert snap.bid_price == 0.80
        assert snap.ask_price == 0.85
        assert snap.mid_price == 0.825
        assert snap.timestamp == now


class TestFillModelConfig:
    def test_defaults(self):
        cfg = FillModelConfig()
        assert cfg.mode == FillMode.PASSIVE
        assert cfg.maker_fee_rate == 0.0
        assert cfg.taker_fee_rate == 0.003
        assert cfg.slippage_bps == 0.0
        assert cfg.queue_position_pct == 0.5
        assert cfg.partial_fill_probability == 0.0

    def test_custom_config(self):
        cfg = FillModelConfig(
            mode=FillMode.TAKER,
            maker_fee_rate=0.001,
            taker_fee_rate=0.003,
            slippage_bps=5.0,
            queue_position_pct=0.3,
            partial_fill_probability=0.1,
        )
        assert cfg.mode == FillMode.TAKER
        assert cfg.slippage_bps == 5.0


class TestFillResult:
    def test_filled_result(self):
        now = datetime.now()
        result = FillResult(
            filled=True,
            fill_price=0.85,
            fill_size=10.0,
            fee=0.0085,
            remaining_size=0.0,
            timestamp=now,
        )
        assert result.filled is True
        assert result.fill_price == 0.85
        assert result.fill_size == 10.0
        assert result.fee == 0.0085
        assert result.remaining_size == 0.0

    def test_unfilled_result(self):
        now = datetime.now()
        result = FillResult(
            filled=False,
            fill_price=0.0,
            fill_size=0.0,
            fee=0.0,
            remaining_size=10.0,
            timestamp=now,
        )
        assert result.filled is False
        assert result.remaining_size == 10.0


class TestFillModel:
    def test_estimate_execution_price_buy(self):
        """A buy order should fill at the ask price (with slippage if configured)."""
        cfg = FillModelConfig(mode=FillMode.TAKER, slippage_bps=0.0)
        model = FillModel(cfg)
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        price = model.estimate_execution_price(OrderSide.BUY, snap)
        assert price == 0.85  # ask price, no slippage

    def test_estimate_execution_price_sell(self):
        """A sell order should fill at the bid price (with slippage if configured)."""
        cfg = FillModelConfig(mode=FillMode.TAKER, slippage_bps=0.0)
        model = FillModel(cfg)
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        price = model.estimate_execution_price(OrderSide.SELL, snap)
        assert price == 0.80  # bid price

    def test_estimate_execution_price_with_slippage(self):
        """Slippage should shift the execution price against the order."""
        cfg = FillModelConfig(mode=FillMode.TAKER, slippage_bps=10.0)  # 0.1%
        model = FillModel(cfg)
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        # Buy at ask (0.85) + 0.1% = 0.85085
        price = model.estimate_execution_price(OrderSide.BUY, snap)
        assert price == pytest.approx(0.85085)

    @pytest.mark.asyncio
    async def test_taker_fill_simulated(self):
        """TAKER mode should always fill immediately."""
        cfg = FillModelConfig(mode=FillMode.TAKER)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.85,
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

    @pytest.mark.asyncio
    async def test_simulate_async(self):
        """simulate() is async and returns a FillResult."""
        cfg = FillModelConfig(mode=FillMode.TAKER)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.SELL,
            price=0.80,
            size=5.0,
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
        assert isinstance(result, FillResult)

    @pytest.mark.asyncio
    async def test_taker_fill_fee_applied(self):
        """Taker fill should apply taker_fee_rate."""
        cfg = FillModelConfig(mode=FillMode.TAKER, taker_fee_rate=0.003)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.85,
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
        assert result.fee == pytest.approx(10.0 * 0.85 * 0.003)  # size * price * fee_rate

    @pytest.mark.asyncio
    async def test_passive_not_filled_when_price_not_crossed(self):
        """PASSIVE mode should not fill when price hasn't crossed."""
        cfg = FillModelConfig(mode=FillMode.PASSIVE)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.80,  # at bid, not crossing
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
        assert result.filled is False
