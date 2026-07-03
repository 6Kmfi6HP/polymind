"""
Tests for the command serializer (OrderSerializer, SerializerConfig, SerializedOrder).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.intents import OrderIntent, OrderSide
from polymind.execution.serializer import (
    OrderSerializer,
    SerializedOrder,
    SerializerConfig,
)


class TestSerializerConfig:
    """SerializerConfig default values and custom construction."""

    def test_default_tick_size(self) -> None:
        cfg = SerializerConfig()
        assert cfg.tick_size == 0.01

    def test_default_min_size(self) -> None:
        cfg = SerializerConfig()
        assert cfg.min_size == 1.0

    def test_default_price_decimals(self) -> None:
        cfg = SerializerConfig()
        assert cfg.price_decimals == 2

    def test_default_size_decimals(self) -> None:
        cfg = SerializerConfig()
        assert cfg.size_decimals == 2

    def test_custom_values(self) -> None:
        cfg = SerializerConfig(
            tick_size=0.001,
            min_size=0.1,
            price_decimals=4,
            size_decimals=3,
        )
        assert cfg.tick_size == 0.001
        assert cfg.min_size == 0.1
        assert cfg.price_decimals == 4
        assert cfg.size_decimals == 3

    def test_all_defaults(self) -> None:
        cfg = SerializerConfig()
        assert cfg.tick_size == 0.01
        assert cfg.min_size == 1.0
        assert cfg.price_decimals == 2
        assert cfg.size_decimals == 2


class TestSerializedOrder:
    """SerializedOrder field assignment and typing."""

    def test_fields_assigned_correctly(self) -> None:
        now = datetime.now()
        order = SerializedOrder(
            market_id="0xabc",
            token_id="0xdef",
            side="BUY",
            price="0.55",
            size="100.00",
            timestamp=now,
        )
        assert order.market_id == "0xabc"
        assert order.token_id == "0xdef"
        assert order.side == "BUY"
        assert order.price == "0.55"
        assert order.size == "100.00"
        assert order.timestamp is now

    def test_separate_instances_are_distinct(self) -> None:
        now = datetime.now()
        a = SerializedOrder(
            market_id="0xaaa",
            token_id="0x111",
            side="BUY",
            price="0.50",
            size="10.00",
            timestamp=now,
        )
        b = SerializedOrder(
            market_id="0xbbb",
            token_id="0x222",
            side="SELL",
            price="0.75",
            size="20.00",
            timestamp=now,
        )
        assert a is not b
        assert a.market_id != b.market_id


class TestOrderSerializerSerializeIntent:
    """OrderIntent -> SerializedOrder conversion."""

    @pytest.fixture
    def serializer(self) -> OrderSerializer:
        return OrderSerializer(SerializerConfig())

    def test_basic_conversion(self, serializer: OrderSerializer) -> None:
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.55,
            size=100.0,
        )
        result = serializer.serialize_intent(intent, token_id="0xdef")
        assert isinstance(result, SerializedOrder)
        assert result.market_id == "0xabc"
        assert result.token_id == "0xdef"
        assert result.side == "BUY"
        assert result.price == "0.55"
        assert result.size == "100.00"
        assert isinstance(result.timestamp, datetime)

    def test_sell_side(self, serializer: OrderSerializer) -> None:
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.SELL,
            price=0.80,
            size=50.0,
        )
        result = serializer.serialize_intent(intent, token_id="0xdef")
        assert result.side == "SELL"

    def test_price_rounding_applied(self, serializer: OrderSerializer) -> None:
        """Off-tick price should be rounded to nearest tick."""
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.557,  # should round to 0.56
            size=100.0,
        )
        result = serializer.serialize_intent(intent, token_id="0xdef")
        assert result.price == "0.56"

    def test_size_rounding_applied(self, serializer: OrderSerializer) -> None:
        """Non-multiple size should be rounded to nearest min_size."""
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.55,
            size=101.5,  # should round to 102.0 (nearest multiple of 1.0)
        )
        result = serializer.serialize_intent(intent, token_id="0xdef")
        assert result.size == "102.00"

    def test_different_token_id(self, serializer: OrderSerializer) -> None:
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.SELL,
            price=0.60,
            size=10.0,
        )
        result = serializer.serialize_intent(intent, token_id="0xtoken123")
        assert result.token_id == "0xtoken123"


class TestOrderSerializerSerializeCancel:
    """Cancel payload generation."""

    @pytest.fixture
    def serializer(self) -> OrderSerializer:
        return OrderSerializer(SerializerConfig())

    def test_returns_dict(self, serializer: OrderSerializer) -> None:
        result = serializer.serialize_cancel(market_id="0xabc", order_id="ord-123")
        assert isinstance(result, dict)

    def test_market_id_key(self, serializer: OrderSerializer) -> None:
        result = serializer.serialize_cancel(market_id="0xabc", order_id="ord-123")
        assert result["market_id"] == "0xabc"

    def test_order_id_key(self, serializer: OrderSerializer) -> None:
        result = serializer.serialize_cancel(market_id="0xabc", order_id="ord-123")
        assert result["order_id"] == "ord-123"

    def test_no_extra_keys(self, serializer: OrderSerializer) -> None:
        result = serializer.serialize_cancel(market_id="0xabc", order_id="ord-123")
        assert set(result.keys()) == {"market_id", "order_id"}


class TestOrderSerializerValidatePrice:
    """Price validation rules."""

    @pytest.fixture
    def serializer(self) -> OrderSerializer:
        return OrderSerializer(SerializerConfig())

    def test_valid_price_passes(self, serializer: OrderSerializer) -> None:
        assert serializer.validate_price(0.50) is True
        assert serializer.validate_price(1.00) is True
        assert serializer.validate_price(0.01) is True

    def test_zero_fails(self, serializer: OrderSerializer) -> None:
        assert serializer.validate_price(0.0) is False

    def test_negative_fails(self, serializer: OrderSerializer) -> None:
        assert serializer.validate_price(-0.50) is False

    def test_off_tick_fails(self, serializer: OrderSerializer) -> None:
        """Price not aligned to tick_size (0.01) should fail."""
        assert serializer.validate_price(0.015) is False
        assert serializer.validate_price(0.123) is False
        assert serializer.validate_price(0.001) is False

    def test_on_tick_passes(self, serializer: OrderSerializer) -> None:
        assert serializer.validate_price(0.01) is True
        assert serializer.validate_price(0.02) is True
        assert serializer.validate_price(0.10) is True
        assert serializer.validate_price(0.55) is True
        assert serializer.validate_price(1.00) is True

    def test_custom_tick_size(self) -> None:
        serializer = OrderSerializer(SerializerConfig(tick_size=0.001))
        assert serializer.validate_price(0.001) is True
        assert serializer.validate_price(0.555) is True
        assert serializer.validate_price(0.5555) is False  # off-tick
        assert serializer.validate_price(0.0) is False


class TestOrderSerializerValidateSize:
    """Size validation rules."""

    @pytest.fixture
    def serializer(self) -> OrderSerializer:
        return OrderSerializer(SerializerConfig())

    def test_valid_size_passes(self, serializer: OrderSerializer) -> None:
        assert serializer.validate_size(1.0) is True
        assert serializer.validate_size(10.0) is True
        assert serializer.validate_size(100.0) is True

    def test_zero_fails(self, serializer: OrderSerializer) -> None:
        assert serializer.validate_size(0.0) is False

    def test_negative_fails(self, serializer: OrderSerializer) -> None:
        assert serializer.validate_size(-10.0) is False

    def test_below_minimum_fails(self, serializer: OrderSerializer) -> None:
        assert serializer.validate_size(0.5) is False
        assert serializer.validate_size(0.99) is False

    def test_non_multiple_fails(self, serializer: OrderSerializer) -> None:
        """Size that is not a multiple of min_size should fail."""
        assert serializer.validate_size(1.5) is False
        assert serializer.validate_size(2.3) is False

    def test_multiple_passes(self, serializer: OrderSerializer) -> None:
        assert serializer.validate_size(2.0) is True
        assert serializer.validate_size(5.0) is True
        assert serializer.validate_size(50.0) is True

    def test_custom_min_size(self) -> None:
        serializer = OrderSerializer(SerializerConfig(min_size=5.0))
        assert serializer.validate_size(5.0) is True
        assert serializer.validate_size(10.0) is True
        assert serializer.validate_size(100.0) is True
        assert serializer.validate_size(4.0) is False  # below min
        assert serializer.validate_size(6.0) is False  # not a multiple
        assert serializer.validate_size(7.5) is False  # not a multiple


class TestOrderSerializerRoundPrice:
    """Price rounding rules."""

    @pytest.fixture
    def serializer(self) -> OrderSerializer:
        return OrderSerializer(SerializerConfig())

    def test_rounds_to_nearest_tick(self, serializer: OrderSerializer) -> None:
        """0.026 with tick=0.01 -> 0.03 (nearest)."""
        assert serializer.round_price(0.026) == pytest.approx(0.03)

    def test_no_rounding_needed(self, serializer: OrderSerializer) -> None:
        assert serializer.round_price(0.55) == pytest.approx(0.55)

    def test_floor_at_tick_size(self, serializer: OrderSerializer) -> None:
        """Values below tick_size floor at tick_size."""
        assert serializer.round_price(0.005) == pytest.approx(0.01)

    def test_negative_returns_tick_size(self, serializer: OrderSerializer) -> None:
        assert serializer.round_price(-5.0) == pytest.approx(0.01)

    def test_zero_returns_tick_size(self, serializer: OrderSerializer) -> None:
        assert serializer.round_price(0.0) == pytest.approx(0.01)

    def test_custom_tick_small(self) -> None:
        serializer = OrderSerializer(SerializerConfig(tick_size=0.5))
        assert serializer.round_price(1.2) == pytest.approx(1.0)
        assert serializer.round_price(1.8) == pytest.approx(2.0)
        assert serializer.round_price(0.1) == pytest.approx(0.5)  # floor

    def test_value_between_ticks_rounds_down(self, serializer: OrderSerializer) -> None:
        """0.023 with tick=0.01 rounds to 0.02 (round half to even or down)."""
        result = serializer.round_price(0.023)
        assert result == pytest.approx(0.02)

    def test_value_between_ticks_rounds_up(self, serializer: OrderSerializer) -> None:
        """0.027 with tick=0.01 rounds to 0.03."""
        result = serializer.round_price(0.027)
        assert result == pytest.approx(0.03)

    def test_exact_half_rounds_to_even(self, serializer: OrderSerializer) -> None:
        """0.025 with tick=0.01 rounds to 0.02 (banker's rounding -> even)."""
        result = serializer.round_price(0.025)
        # round(2.5) = 2 in Python 3 -> 0.02
        assert result == pytest.approx(0.02)


class TestOrderSerializerRoundSize:
    """Size rounding rules."""

    @pytest.fixture
    def serializer(self) -> OrderSerializer:
        return OrderSerializer(SerializerConfig())

    def test_rounds_to_nearest_min_size(self, serializer: OrderSerializer) -> None:
        """101.5 with min_size=1.0 -> 102.0 (nearest)."""
        assert serializer.round_size(101.5) == pytest.approx(102.0)

    def test_no_rounding_needed(self, serializer: OrderSerializer) -> None:
        assert serializer.round_size(100.0) == pytest.approx(100.0)

    def test_floor_at_min_size(self, serializer: OrderSerializer) -> None:
        """Values below min_size floor at min_size."""
        assert serializer.round_size(0.5) == pytest.approx(1.0)

    def test_negative_returns_min_size(self, serializer: OrderSerializer) -> None:
        assert serializer.round_size(-5.0) == pytest.approx(1.0)

    def test_zero_returns_min_size(self, serializer: OrderSerializer) -> None:
        assert serializer.round_size(0.0) == pytest.approx(1.0)

    def test_custom_min_size(self) -> None:
        serializer = OrderSerializer(SerializerConfig(min_size=5.0))
        assert serializer.round_size(5.0) == pytest.approx(5.0)
        assert serializer.round_size(8.0) == pytest.approx(10.0)
        assert serializer.round_size(2.0) == pytest.approx(5.0)  # floor

    def test_value_between_increments_rounds_down(self, serializer: OrderSerializer) -> None:
        """12.3 with min_size=1.0 rounds to 12.0."""
        result = serializer.round_size(12.3)
        assert result == pytest.approx(12.0)

    def test_value_between_increments_rounds_up(self, serializer: OrderSerializer) -> None:
        """12.7 with min_size=1.0 rounds to 13.0."""
        result = serializer.round_size(12.7)
        assert result == pytest.approx(13.0)


class TestOrderSerializerEdgeCases:
    """Edge cases for all serializer methods."""

    @pytest.fixture
    def serializer(self) -> OrderSerializer:
        return OrderSerializer(SerializerConfig())

    def test_very_small_price_rounds_to_tick(self, serializer: OrderSerializer) -> None:
        """Extremely small price floors to tick_size."""
        assert serializer.round_price(1e-9) == pytest.approx(0.01)

    def test_very_small_size_rounds_to_min(self, serializer: OrderSerializer) -> None:
        """Extremely small size floors to min_size."""
        assert serializer.round_size(1e-9) == pytest.approx(1.0)

    def test_large_values_still_valid(self, serializer: OrderSerializer) -> None:
        """Large prices and sizes should work correctly."""
        assert serializer.validate_price(1_000_000.00) is True
        assert serializer.validate_size(1_000_000.0) is True

    def test_validate_price_near_tick_boundary(self, serializer: OrderSerializer) -> None:
        """Floating point values near tick_size boundary."""
        assert serializer.validate_price(0.0100001) is False
        assert serializer.validate_price(0.0099999) is False

    def test_validate_size_near_min_boundary(self, serializer: OrderSerializer) -> None:
        """Size values near min_size boundary."""
        assert serializer.validate_size(0.999999) is False
        assert serializer.validate_size(1.0) is True  # exactly min_size

    def test_round_price_non_standard_tick(self) -> None:
        """Tick sizes that are not 0.01."""
        serializer = OrderSerializer(SerializerConfig(tick_size=0.25))
        assert serializer.round_price(0.10) == pytest.approx(0.25)  # floor
        assert serializer.round_price(0.60) == pytest.approx(0.50)  # rounds down
        assert serializer.round_price(0.70) == pytest.approx(0.75)  # rounds up
        assert serializer.round_price(1.00) == pytest.approx(1.00)

    def test_round_size_non_standard_min(self) -> None:
        """Min sizes that are not 1.0."""
        serializer = OrderSerializer(SerializerConfig(min_size=2.5))
        assert serializer.round_size(1.0) == pytest.approx(2.5)  # floor
        assert serializer.round_size(3.0) == pytest.approx(2.5)  # rounds down
        assert serializer.round_size(4.0) == pytest.approx(5.0)  # rounds up
        assert serializer.round_size(5.0) == pytest.approx(5.0)

    def test_serialize_intent_sub_min_values(self, serializer: OrderSerializer) -> None:
        """Intents with sub-minimum price/size should be brought up to minimum."""
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.001,
            size=0.001,
        )
        result = serializer.serialize_intent(intent, token_id="0xdef")
        # Both should floor to minimum allowed values
        assert result.price == "0.01"
        assert result.size == "1.00"

    def test_serialize_intent_custom_decimals(self) -> None:
        """Custom decimal places in config should be reflected in formatted strings."""
        serializer = OrderSerializer(SerializerConfig(price_decimals=4, size_decimals=3))
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.SELL,
            price=0.55,
            size=100.0,
        )
        result = serializer.serialize_intent(intent, token_id="0xdef")
        assert result.price == "0.5500"
        assert result.size == "100.000"
