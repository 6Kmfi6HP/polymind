"""
Tests for FillEvent and FillSource.
"""

from __future__ import annotations

from datetime import datetime, timezone

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import OrderSide


class TestFillSource:
    def test_enum_values(self):
        assert FillSource.WEBSOCKET != FillSource.CLOB_API
        assert FillSource.ONCHAIN != FillSource.SIMULATED

    def test_all_sources_defined(self):
        expected = {"WEBSOCKET", "CLOB_API", "ONCHAIN", "SIMULATED"}
        assert {e.name for e in FillSource} == expected


class TestFillEvent:
    def test_minimal_construction(self):
        now = datetime.now(timezone.utc)
        event = FillEvent(
            fill_id="fill-001",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.WEBSOCKET,
        )
        assert event.fill_id == "fill-001"
        assert event.market_id == "0xabc"
        assert event.outcome == "YES"
        assert event.side == OrderSide.BUY
        assert event.price == 0.85
        assert event.size == 10.0
        assert event.fee == 0.01
        assert event.timestamp == now
        assert event.source == FillSource.WEBSOCKET
        assert event.order_id is None
        assert event.taker is False

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        event = FillEvent(
            fill_id="fill-002",
            market_id="0xdef",
            outcome="NO",
            side=OrderSide.SELL,
            price=0.12,
            size=5.0,
            fee=0.005,
            timestamp=now,
            source=FillSource.CLOB_API,
            order_id="ord-456",
            taker=True,
            metadata={"retry_count": 0},
        )
        assert event.order_id == "ord-456"
        assert event.taker is True
        assert event.metadata["retry_count"] == 0

    def test_simulated_source(self):
        now = datetime.now(timezone.utc)
        event = FillEvent(
            fill_id="fill-sim-001",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.80,
            size=100.0,
            fee=0.0,
            timestamp=now,
            source=FillSource.SIMULATED,
        )
        assert event.source == FillSource.SIMULATED
        assert event.fee == 0.0
