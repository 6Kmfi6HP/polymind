"""
Tests for OrderIdentity.
"""

from __future__ import annotations

import pytest

from polymind.core.intents import OrderSide
from polymind.execution.order_identity import OrderIdentity


class TestOrderIdentity:
    def test_minimal_construction(self):
        oid = OrderIdentity(
            strategy_name="test_strat",
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.85,
            outcome="YES",
            client_id="client-001",
        )
        assert oid.strategy_name == "test_strat"
        assert oid.market_id == "0xabc"
        assert oid.side == OrderSide.BUY
        assert oid.price == 0.85
        assert oid.outcome == "YES"
        assert oid.client_id == "client-001"

    def test_construction_without_outcome(self):
        oid = OrderIdentity(
            strategy_name="test_strat",
            market_id="0xabc",
            side=OrderSide.SELL,
            price=0.75,
            outcome=None,
            client_id="client-002",
        )
        assert oid.outcome is None

    def test_frozen_dataclass(self):
        oid = OrderIdentity(
            strategy_name="test",
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.5,
            outcome="NO",
            client_id="c1",
        )
        with pytest.raises(AttributeError):
            oid.strategy_name = "changed"  # type: ignore[misc]

    def test_hashable(self):
        oid1 = OrderIdentity(
            strategy_name="s1",
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.5,
            outcome="YES",
            client_id="c1",
        )
        oid2 = OrderIdentity(
            strategy_name="s1",
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.5,
            outcome="YES",
            client_id="c1",
        )
        s = {oid1, oid2}
        assert len(s) == 1  # same fields → same hash

    def test_usable_as_dict_key(self):
        oid = OrderIdentity(
            strategy_name="s1",
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.5,
            outcome="YES",
            client_id="c1",
        )
        d = {oid: "found"}
        assert d[oid] == "found"

    def test_identity_string_format(self):
        oid = OrderIdentity(
            strategy_name="strat1",
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.85,
            outcome="YES",
            client_id="cli-1",
        )
        expected = "strat1:0xabc:BUY:0.85:YES:cli-1"
        assert oid.to_identity_string() == expected

    def test_identity_string_without_outcome(self):
        oid = OrderIdentity(
            strategy_name="strat1",
            market_id="0xdef",
            side=OrderSide.SELL,
            price=0.12,
            outcome=None,
            client_id="cli-2",
        )
        expected = "strat1:0xdef:SELL:0.12:_:cli-2"
        assert oid.to_identity_string() == expected
