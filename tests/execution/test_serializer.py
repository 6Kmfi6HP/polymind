"""
Tests for SerializerConfig, SerializedOrder, and OrderSerializer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import pytest

from polymind.core.intents import OrderIntent, OrderSide
from polymind.execution.serializer import (
    OrderSerializer,
    SerializedOrder,
    SerializerConfig,
)


class TestSerializerConfig:
    def test_defaults(self) -> None:
        cfg = SerializerConfig()
        assert cfg.tick_size == 0.01
        assert cfg.min_size == 1.0
        assert cfg.price_decimals == 2
        assert cfg.size_decimals == 2

    def test_custom_values(self) -> None:
        cfg = SerializerConfig(tick_size=0.001, min_size=0.1, price_decimals=3, size_decimals=1)
        assert cfg.tick_size == 0.001
        assert cfg.min_size == 0.1
        assert cfg.price_decimals == 3
        assert cfg.size_decimals == 1


class TestSerializedOrder:
    def test_construction(self) -> None:
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
        assert order.timestamp == now


class TestOrderSerializer:
    @pytest.fixture
    def config(self) -> SerializerConfig:
        return SerializerConfig(tick_size=0.01, min_size=1.0)

    @pytest.fixture
    def serializer(self, config: SerializerConfig) -> OrderSerializer:
        return OrderSerializer(config)

    # ── serialize_intent ─────────────────────────────────────────────────

    def test_serialize_intent_creates_correct_format(
        self, serializer: OrderSerializer
    ) -> None:
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.556,
            size=10.0,
        )
        result = serializer.serialize_intent(intent, token_id="0xdef")

        assert result.market_id == "0xabc"
        assert result.token_id == "0xdef"
        assert result.side == "BUY"
        assert result.price == "0.56"  # rounded to tick_size
        assert result.size == "10.00"
        assert isinstance(result.timestamp, datetime)

    def test_serialize_intent_rounds_price_to_tick(
        self, serializer: OrderSerializer
    ) -> None:
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.SELL,
            price=1.234,
            size=5.0,
        )
        result = serializer.serialize_intent(intent, token_id="0x1")
        assert result.price == "1.23"

    def test_serialize_intent_rounds_size_to_min(
        self, serializer: OrderSerializer
    ) -> None:
        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.SELL,
            price=0.50,
            size=3.7,
        )
        result = serializer.serialize_intent(intent, token_id="0x1")
        assert result.size == "4.00"  # 3.7 rounds to 4 (nearest 1.0)

    # ── serialize_cancel ─────────────────────────────────────────────────

    def test_serialize_cancel(self, serializer: OrderSerializer) -> None:
        result = serializer.serialize_cancel("0xabc", "order-123")
        assert isinstance(result, dict)
        assert result["market_id"] == "0xabc"
        assert result["order_id"] == "order-123"

    # ── validate_price ───────────────────────────────────────────────────

    @pytest.mark.parametrize(
        ("price", "expected"),
        [
            (0.01, True),   # exactly one tick
            (0.05, True),   # 5 ticks
            (1.00, True),   # 100 ticks
            (0.0, False),   # zero
            (-0.01, False), # negative
            (0.005, False), # sub-tick (< 0.01)
            (0.015, False), # between ticks
        ],
    )
    def test_validate_price(
        self, serializer: OrderSerializer, price: float, expected: bool
    ) -> None:
        assert serializer.validate_price(price) == expected

    # ── validate_size ────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        ("size", "expected"),
        [
            (1.0, True),     # exactly min_size
            (5.0, True),     # multiple of min_size
            (10.0, True),    # multiple of min_size
            (0.0, False),    # zero
            (-1.0, False),   # negative
            (0.5, False),    # below min_size
            (1.5, False),    # not a multiple of min_size
            (2.5, False),    # not a multiple of min_size
        ],
    )
    def test_validate_size(
        self, serializer: OrderSerializer, size: float, expected: bool
    ) -> None:
        assert serializer.validate_size(size) == expected

    # ── round_price ──────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        ("price", "expected"),
        [
            (0.556, 0.56),
            (0.554, 0.55),
            (1.238, 1.24),
            (0.001, 0.01),  # below tick → tick_size
            (-0.5, 0.01),   # negative → tick_size
            (0.01, 0.01),   # exactly one tick
            (0.10, 0.10),   # multiple of tick
        ],
    )
    def test_round_price(
        self, serializer: OrderSerializer, price: float, expected: float
    ) -> None:
        assert serializer.round_price(price) == pytest.approx(expected)

    # ── round_size ───────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        ("size", "expected"),
        [
            (3.7, 4.0),     # nearest min_size
            (0.5, 1.0),     # below min → min_size
            (1.0, 1.0),     # exactly min_size
            (5.2, 5.0),     # nearest min_size
            (5.8, 6.0),     # nearest min_size
            (-1.0, 1.0),    # negative → min_size
        ],
    )
    def test_round_size(
        self, serializer: OrderSerializer, size: float, expected: float
    ) -> None:
        assert serializer.round_size(size) == pytest.approx(expected)

    # ── Edge cases with custom config ────────────────────────────────────

    def test_small_tick_serializer(self) -> None:
        cfg = SerializerConfig(tick_size=0.001, min_size=0.1, price_decimals=3, size_decimals=1)
        ser = OrderSerializer(cfg)

        intent = OrderIntent(
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.1234,
            size=2.35,
        )
        result = ser.serialize_intent(intent, token_id="0x1")
        assert result.price == "0.123"
        assert result.size == "2.4"

        assert ser.validate_price(0.123) is True
        assert ser.validate_price(0.122) is True   # 122 * 0.001 = 0.122
        assert ser.validate_price(0.120) is True   # 120 * 0.001
        assert ser.validate_price(0.1225) is False  # not a multiple of 0.001

        assert ser.validate_size(0.2) is True
        assert ser.validate_size(0.15) is False  # not multiple of 0.1

    def test_round_price_high_tick(self) -> None:
        cfg = SerializerConfig(tick_size=0.5, min_size=1.0)
        ser = OrderSerializer(cfg)

        assert ser.round_price(0.6) == pytest.approx(0.5)
        assert ser.round_price(0.9) == pytest.approx(1.0)
        assert ser.round_price(1.2) == pytest.approx(1.0)
        assert ser.round_price(1.3) == pytest.approx(1.5)
