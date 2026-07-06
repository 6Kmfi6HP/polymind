"""
Tests for execution models.
"""

from __future__ import annotations

from datetime import datetime

from polymind.backtesting.execution_model import (
    ExecutionModelConfig,
    PassiveExecutionModel,
    TakerExecutionModel,
)
from polymind.core.intents import OrderIntent, OrderSide
from polymind.execution.fill_model import MarketSnapshot


def _snapshot(
    bid: float = 1.0,
    ask: float = 1.1,
    mid: float = 1.05,
    bid_size: float = 1000.0,
    ask_size: float = 1000.0,
    market_id: str = "0xabc",
    ts: datetime | None = None,
) -> MarketSnapshot:
    return MarketSnapshot(
        market_id=market_id,
        bid_price=bid,
        bid_size=bid_size,
        ask_price=ask,
        ask_size=ask_size,
        mid_price=mid,
        timestamp=ts or datetime.now(),
    )


def _intent(
    side: OrderSide,
    price: float,
    size: float = 100.0,
    market_id: str = "0xabc",
) -> OrderIntent:
    return OrderIntent(
        market_id=market_id,
        side=side,
        price=price,
        size=size,
    )


class TestExecutionModelConfig:
    def test_defaults(self) -> None:
        config = ExecutionModelConfig()
        assert config.slippage_bps == 0.0
        assert config.latency_ms == 0.0
        assert config.partial_fill_prob == 0.0
        assert config.queue_position_pct == 0.0


class TestPassiveExecutionModel:
    def test_no_fill_when_price_not_crossed_buy(self) -> None:
        model = PassiveExecutionModel(ExecutionModelConfig())
        snap = _snapshot(bid=1.0, ask=1.1)
        intent = _intent(OrderSide.BUY, price=1.05)  # below ask, no cross

        result = model.simulate_fill(intent, snap)

        assert result.filled is False
        assert result.fill_price == 0.0
        assert result.fill_size == 0.0
        assert result.fee == 0.0
        assert result.remaining_size == 100.0

    def test_no_fill_when_price_not_crossed_sell(self) -> None:
        model = PassiveExecutionModel(ExecutionModelConfig())
        snap = _snapshot(bid=1.0, ask=1.1)
        intent = _intent(OrderSide.SELL, price=1.05)  # above bid, no cross

        result = model.simulate_fill(intent, snap)

        assert result.filled is False
        assert result.remaining_size == 100.0

    def test_fill_when_price_crossed_buy(self) -> None:
        model = PassiveExecutionModel(ExecutionModelConfig())
        snap = _snapshot(bid=1.0, ask=1.1)
        intent = _intent(OrderSide.BUY, price=1.1)  # >= ask, crosses

        result = model.simulate_fill(intent, snap)

        assert result.filled is True
        assert result.fill_price == 1.1
        assert result.fill_size == 100.0
        assert result.remaining_size == 0.0

    def test_fill_when_price_crossed_sell(self) -> None:
        model = PassiveExecutionModel(ExecutionModelConfig())
        snap = _snapshot(bid=1.0, ask=1.1)
        intent = _intent(OrderSide.SELL, price=1.0)  # <= bid, crosses

        result = model.simulate_fill(intent, snap)

        assert result.filled is True
        assert result.fill_price == 1.0
        assert result.fill_size == 100.0
        assert result.remaining_size == 0.0

    def test_estimate_queue_position_zero_depth(self) -> None:
        """When book depth is zero, returns the configured pct."""
        model = PassiveExecutionModel(ExecutionModelConfig(queue_position_pct=0.3))
        snap = _snapshot(bid=0.0, ask=0.0, bid_size=0.0, ask_size=0.0)
        pos = model.estimate_queue_position(1.0, snap)
        assert pos == 0.3

    def test_estimate_queue_position_adjusts_downward(self) -> None:
        """Queue position improves (goes toward 0) with depth."""
        model = PassiveExecutionModel(ExecutionModelConfig(queue_position_pct=0.5))
        snap = _snapshot(bid=1.0, ask=1.1, bid_size=10.0, ask_size=10.0)
        pos = model.estimate_queue_position(1.05, snap)
        # 0.5 * (1 / (1 + 20)) = 0.5 / 21 ≈ 0.0238
        assert pos < 0.5
        assert pos > 0.0


class TestTakerExecutionModel:
    def test_buy_fills_at_ask_with_slippage(self) -> None:
        model = TakerExecutionModel(ExecutionModelConfig(slippage_bps=10.0))
        snap = _snapshot(bid=1.0, ask=1.1)
        intent = _intent(OrderSide.BUY, price=1.15)

        result = model.simulate_fill(intent, snap)

        assert result.filled is True
        # base ask=1.1, slippage=10bps => 1.1 * 1.001 = 1.1011
        expected_price = 1.1 * 1.001
        assert result.fill_price == expected_price
        assert result.fill_size == 100.0
        assert result.remaining_size == 0.0

    def test_sell_fills_at_bid_with_slippage(self) -> None:
        model = TakerExecutionModel(ExecutionModelConfig(slippage_bps=10.0))
        snap = _snapshot(bid=1.0, ask=1.1)
        intent = _intent(OrderSide.SELL, price=0.95)

        result = model.simulate_fill(intent, snap)

        assert result.filled is True
        # base bid=1.0, slippage=10bps => 1.0 * 0.999 = 0.999
        expected_price = 1.0 * 0.999
        assert result.fill_price == expected_price
        assert result.fill_size == 100.0
        assert result.remaining_size == 0.0

    def test_estimate_slippage_zero_when_small(self) -> None:
        model = TakerExecutionModel(ExecutionModelConfig())
        slp = model.estimate_slippage(10.0, 1000.0)  # ratio = 0.01
        assert slp == 0.0

    def test_estimate_slippage_linear_medium(self) -> None:
        model = TakerExecutionModel(ExecutionModelConfig())
        slp = model.estimate_slippage(300.0, 1000.0)  # ratio = 0.3
        # 0.3 * 5.0 = 1.5 bps
        assert slp == 1.5

    def test_estimate_slippage_linear_large(self) -> None:
        model = TakerExecutionModel(ExecutionModelConfig())
        slp = model.estimate_slippage(800.0, 1000.0)  # ratio = 0.8
        # 0.8 * 10.0 = 8.0 bps
        assert slp == 8.0

    def test_estimate_slippage_capped(self) -> None:
        model = TakerExecutionModel(ExecutionModelConfig())
        slp = model.estimate_slippage(5000.0, 1000.0)  # ratio = 5.0
        assert slp == 20.0

    def test_estimate_slippage_zero_liquidity(self) -> None:
        model = TakerExecutionModel(ExecutionModelConfig())
        slp = model.estimate_slippage(100.0, 0.0)
        assert slp == 0.0


class TestMicroPriceSignalOnly:
    """REF-008: Micro-price used as signal-only in execution models.

    Backtesting execution models must use executable bid/ask for fill
    prices — never micro_price, fair_value, or mid_price.
    """

    def test_taker_buy_uses_ask_not_micro_price(self) -> None:
        """Taker BUY must use ask_price for fill, never micro_price."""
        model = TakerExecutionModel(ExecutionModelConfig(slippage_bps=0))
        # Use small order (ratio <= 0.1 of book) to avoid additional slippage
        snap = _snapshot(bid=0.40, ask=0.60, mid=0.50, bid_size=5000.0, ask_size=500.0)
        intent = _intent(OrderSide.BUY, price=0.65, size=50.0)  # ratio = 50/500 = 0.1

        result = model.simulate_fill(intent, snap)

        assert result.filled
        # Should fill at ask (0.60), not at micro_price (~0.582) or mid (0.50)
        assert (
            result.fill_price == 0.60
        ), f"Taker BUY fill must use ask (0.60), got {result.fill_price}"

    def test_taker_sell_uses_bid_not_micro_price(self) -> None:
        """Taker SELL must use bid_price for fill, never micro_price."""
        model = TakerExecutionModel(ExecutionModelConfig(slippage_bps=0))
        # Use small order (ratio <= 0.1 of book) to avoid additional slippage
        snap = _snapshot(bid=0.40, ask=0.60, mid=0.50, bid_size=5000.0, ask_size=500.0)
        intent = _intent(OrderSide.SELL, price=0.35, size=50.0)  # ratio = 50/5000 = 0.01

        result = model.simulate_fill(intent, snap)

        assert result.filled
        assert (
            result.fill_price == 0.40
        ), f"Taker SELL fill must use bid (0.40), got {result.fill_price}"

    def test_passive_cross_check_uses_ask_not_mid(self) -> None:
        """Passive BUY cross check uses ask_price, not mid or micro_price.

        A BUY order at 0.55 should NOT fill when ask is 0.60, even though
        mid (0.50) is below the order price.  Using mid as fill-cross
        threshold would incorrectly consider this crossed.
        """
        model = PassiveExecutionModel(ExecutionModelConfig())
        snap = _snapshot(bid=0.40, ask=0.60, mid=0.50)
        intent = _intent(OrderSide.BUY, price=0.55)  # above mid, below ask

        result = model.simulate_fill(intent, snap)

        # Must NOT fill — spread hasn't been crossed (ask 0.60 > price 0.55)
        assert not result.filled, (
            "Passive BUY at 0.55 must not fill when ask is 0.60 " "(mid 0.50 is not the fill price)"
        )

    def test_execution_model_src_has_no_micro_price_reference(self) -> None:
        """Structural: execution_model.py must not reference micro_price or fair_value."""
        import inspect

        import polymind.backtesting.execution_model as em

        src = inspect.getsource(em)
        assert "micro_price" not in src, "execution_model must not reference micro_price"
        assert "fair_value" not in src, "execution_model must not reference fair_value"
