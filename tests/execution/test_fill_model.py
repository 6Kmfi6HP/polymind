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

    @pytest.mark.asyncio
    async def test_passive_sell_crossed(self):
        """PASSIVE SELL fills when price ≤ bid (line 149)."""
        cfg = FillModelConfig(mode=FillMode.PASSIVE)
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.SELL,
            price=0.80,  # <= bid=0.80 → crossed
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
        assert result.fill_price == 0.80

    @pytest.mark.asyncio
    async def test_passive_queue_front_always_fills(self):
        """queue_position_pct=0.0 (front of queue) should always fill when crossed."""
        cfg = FillModelConfig(mode=FillMode.PASSIVE, queue_position_pct=0.0)
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
        # Run multiple times to confirm deterministic behaviour
        for _ in range(10):
            result = await model.simulate(intent, snap)
            assert result.filled is True
            assert result.fill_size == 10.0

    @pytest.mark.asyncio
    async def test_passive_queue_back_never_fills(self):
        """queue_position_pct=1.0 (back of queue) should never fill even when crossed."""
        cfg = FillModelConfig(mode=FillMode.PASSIVE, queue_position_pct=1.0)
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
        for _ in range(10):
            result = await model.simulate(intent, snap)
            assert result.filled is False
            assert result.remaining_size == 10.0

    @pytest.mark.asyncio
    async def test_passive_queue_half_probabilistic(self):
        """queue_position_pct=0.5 should allow fills with ~50% probability, deterministic.

        Since the fill determinant is a hash, the result is deterministic but
        we confirm it produces *some* fills and *some* non-fills across
        different intents with the same queue position.
        """
        cfg = FillModelConfig(mode=FillMode.PASSIVE, queue_position_pct=0.5)
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
        results = set()
        for i in range(20):
            intent = OrderIntent(
                market_id=f"0x{i:04x}",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
            )
            result = await model.simulate(intent, snap)
            results.add(result.filled)
        # With 20 different market IDs, we should see both fills and non-fills
        assert results == {True, False}

    @pytest.mark.asyncio
    async def test_passive_partial_fill(self):
        """partial_fill_probability > 0 should leave remaining_size."""
        cfg = FillModelConfig(
            mode=FillMode.PASSIVE,
            queue_position_pct=0.0,  # front of queue
            partial_fill_probability=0.3,
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
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        result = await model.simulate(intent, snap)
        assert result.filled is True
        # With 30% partial fill probability, 30% stays unfilled
        assert result.fill_size == 70.0  # 100 * (1 - 0.3)
        assert result.remaining_size == 30.0

    @pytest.mark.asyncio
    async def test_passive_partial_fill_zero(self):
        """partial_fill_probability=0.0 means full fill (no partial)."""
        cfg = FillModelConfig(
            mode=FillMode.PASSIVE,
            queue_position_pct=0.0,
            partial_fill_probability=0.0,
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
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        result = await model.simulate(intent, snap)
        assert result.filled is True
        assert result.fill_size == 100.0
        assert result.remaining_size == 0.0

    @pytest.mark.asyncio
    async def test_passive_partial_fill_all(self):
        """partial_fill_probability=1.0 means nothing fills."""
        cfg = FillModelConfig(
            mode=FillMode.PASSIVE,
            queue_position_pct=0.0,
            partial_fill_probability=1.0,
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
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        result = await model.simulate(intent, snap)
        assert result.filled is True
        assert result.fill_size == 0.0
        assert result.remaining_size == 100.0

    @pytest.mark.asyncio
    async def test_passive_queue_and_partial_combined(self):
        """Queue position AND partial fill applied together."""
        # At queue_position_pct=0.5 and partial_fill_probability=0.25,
        # when the queue allows a fill, only 75% fills.
        cfg = FillModelConfig(
            mode=FillMode.PASSIVE,
            queue_position_pct=0.5,
            partial_fill_probability=0.25,
        )
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
        # Use a market ID known to pass the queue check
        intent = OrderIntent(
            market_id="0xpass",
            side=OrderSide.BUY,
            price=0.85,
            size=100.0,
        )
        result = await model.simulate(intent, snap)
        if result.filled:
            assert result.fill_size == 75.0
            assert result.remaining_size == 25.0

    @pytest.mark.asyncio
    async def test_passive_deterministic_reproducible(self):
        """Same intent + snapshot produces the same result every time."""
        cfg = FillModelConfig(
            mode=FillMode.PASSIVE,
            queue_position_pct=0.3,
            partial_fill_probability=0.1,
        )
        model = FillModel(cfg)
        intent = OrderIntent(
            market_id="0xdeterministic",
            side=OrderSide.BUY,
            price=0.85,
            size=100.0,
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
        # Run twice
        r1 = await model.simulate(intent, snap)
        r2 = await model.simulate(intent, snap)
        assert r1.filled == r2.filled
        assert r1.fill_size == r2.fill_size
        assert r1.remaining_size == r2.remaining_size

    @pytest.mark.asyncio
    async def test_passive_backward_compatible_default(self):
        """Default config (queue=0.5, partial=0.0) should maintain existing behaviour:
        crossing → fills (deterministic check may prevent some fills at 0.5)."""
        cfg = FillModelConfig(mode=FillMode.PASSIVE)  # defaults: queue=0.5, partial=0.0
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
        # With queue_position_pct=0.5, some intents will fill and some won't.
        # Confirm the implementation doesn't crash and returns correct types.
        for i in range(5):
            intent = OrderIntent(
                market_id=f"0x{i:04x}",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
            )
            result = await model.simulate(intent, snap)
            assert isinstance(result.filled, bool)
            assert isinstance(result.fill_size, float)
            assert isinstance(result.remaining_size, float)

    @pytest.mark.asyncio
    async def test_estimate_execution_price_sell_with_slippage(self):
        """SELL side with slippage (line 94)."""
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
        price = model.estimate_execution_price(OrderSide.SELL, snap)
        # Bid 0.80 - 0.1% = 0.7992
        assert price == pytest.approx(0.7992)


class TestMicroPriceSignalOnly:
    """REF-008: Micro-price used as signal-only, never as fill price.

    The polymarket-quant reference project treats micro-price and fair-value
    as signal features only.  FillModel must use executable bid/ask for fill
    prices — never micro_price, fair_value, or mid_price.
    """

    def test_estimate_execution_price_buy_uses_ask_not_micro_price(self) -> None:
        """BUY fill price must be ask_price, not mid or micro_price."""
        now = datetime.now()
        snap = MarketSnapshot(
            market_id="0x1",
            bid_price=0.40,
            bid_size=5000.0,
            ask_price=0.60,
            ask_size=500.0,
            mid_price=0.50,
            timestamp=now,
        )
        model = FillModel(FillModelConfig(mode=FillMode.TAKER, slippage_bps=0))

        price = model.estimate_execution_price(OrderSide.BUY, snap)

        # With asymmetric liquidity, micro_price ≈ 0.582, mid = 0.50.
        # BUY fill must use ask (0.60), not mid or micro_price.
        assert price == 0.60, f"BUY fill must use ask_price (0.60), got {price}"

    def test_estimate_execution_price_sell_uses_bid_not_micro_price(self) -> None:
        """SELL fill price must be bid_price, not mid or micro_price."""
        now = datetime.now()
        snap = MarketSnapshot(
            market_id="0x1",
            bid_price=0.40,
            bid_size=5000.0,
            ask_price=0.60,
            ask_size=500.0,
            mid_price=0.50,
            timestamp=now,
        )
        model = FillModel(FillModelConfig(mode=FillMode.TAKER, slippage_bps=0))

        price = model.estimate_execution_price(OrderSide.SELL, snap)

        assert price == 0.40, f"SELL fill must use bid_price (0.40), got {price}"

    def test_fill_model_src_has_no_micro_price_reference(self) -> None:
        """Structural: FillModel source must not reference micro_price or fair_value."""
        import inspect

        import polymind.execution.fill_model as fm

        src = inspect.getsource(fm)
        assert "micro_price" not in src, "FillModel must not reference micro_price"
        assert "fair_value" not in src, "FillModel must not reference fair_value"
