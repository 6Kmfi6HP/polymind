"""
Tests for OrderManager — centralized order lifecycle tracking.
"""

from __future__ import annotations

from datetime import datetime

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import OrderIntent, OrderSide
from polymind.execution.order_identity import OrderIdentity
from polymind.execution.order_manager import (
    OrderManager,
    OrderStatus,
)


def _identity(
    strategy: str = "test",
    market: str = "mkt1",
    side: OrderSide = OrderSide.BUY,
    price: float = 0.5,
    client_id: str = "c1",
) -> OrderIdentity:
    return OrderIdentity(
        strategy_name=strategy,
        market_id=market,
        side=side,
        price=price,
        outcome="YES",
        client_id=client_id,
    )


def _intent(
    market: str = "mkt1", side: OrderSide = OrderSide.BUY, price: float = 0.5, size: float = 10.0
) -> OrderIntent:
    return OrderIntent(market_id=market, side=side, price=price, size=size, outcome="YES")


class TestOrderManager:
    def test_add_order(self):
        mgr = OrderManager()
        ident = _identity()
        order = mgr.add_order(ident, _intent(), "exch1")
        assert order.identity is ident
        assert order.status == OrderStatus.OPEN
        assert order.exchange_order_id == "exch1"

    def test_add_order_pending_without_exchange_id(self):
        mgr = OrderManager()
        order = mgr.add_order(_identity(), _intent())
        assert order.status == OrderStatus.PENDING

    def test_add_duplicate_raises(self):
        mgr = OrderManager()
        mgr.add_order(_identity(), _intent())
        import pytest

        with pytest.raises(ValueError, match="already tracked"):
            mgr.add_order(_identity(), _intent())

    def test_get_order(self):
        mgr = OrderManager()
        mgr.add_order(_identity(), _intent())
        order = mgr.get_order(_identity().to_identity_string())
        assert order is not None

    def test_get_order_nonexistent(self):
        mgr = OrderManager()
        assert mgr.get_order("nope") is None

    def test_update_status(self):
        mgr = OrderManager()
        mgr.add_order(_identity(), _intent())
        key = _identity().to_identity_string()
        updated = mgr.update_status(key, OrderStatus.FILLED, filled_size=10.0)
        assert updated is not None
        assert updated.status == OrderStatus.FILLED
        assert updated.filled_size == 10.0

    def test_update_status_nonexistent(self):
        mgr = OrderManager()
        assert mgr.update_status("nope", OrderStatus.FILLED) is None

    def test_get_open_orders(self):
        mgr = OrderManager()
        mgr.add_order(_identity(client_id="c1"), _intent())
        mgr.add_order(_identity(client_id="c2"), _intent(), "exch2")
        mgr.cancel_order(_identity(client_id="c1").to_identity_string())
        open_orders = mgr.get_open_orders()
        assert len(open_orders) == 1
        assert open_orders[0].identity.client_id == "c2"

    def test_get_open_orders_filtered(self):
        mgr = OrderManager()
        mgr.add_order(_identity(market="mkt1"), _intent(market="mkt1"), "e1")
        mgr.add_order(_identity(market="mkt2"), _intent(market="mkt2"), "e2")
        open_orders = mgr.get_open_orders(market_id="mkt1")
        assert len(open_orders) == 1
        assert open_orders[0].identity.market_id == "mkt1"

    def test_get_orders_by_strategy(self):
        mgr = OrderManager()
        mgr.add_order(_identity(strategy="strat_a", client_id="c1"), _intent(), "e1")
        mgr.add_order(_identity(strategy="strat_a", client_id="c2"), _intent(), "e2")
        mgr.add_order(_identity(strategy="strat_b", client_id="c3"), _intent(), "e3")
        orders = mgr.get_orders_by_strategy("strat_a")
        assert len(orders) == 2

    def test_cancel_order(self):
        mgr = OrderManager()
        mgr.add_order(_identity(), _intent())
        assert mgr.cancel_order(_identity().to_identity_string()) is True

    def test_cancel_nonexistent(self):
        mgr = OrderManager()
        assert mgr.cancel_order("nope") is False

    def test_cancel_all(self):
        mgr = OrderManager()
        mgr.add_order(_identity(client_id="c1"), _intent(), "e1")
        mgr.add_order(_identity(client_id="c2"), _intent(), "e2")
        mgr.add_order(_identity(client_id="c3"), _intent(), "e3")
        count = mgr.cancel_all()
        assert count == 3
        assert len(mgr.get_open_orders()) == 0

    def test_cancel_all_filtered(self):
        mgr = OrderManager()
        mgr.add_order(_identity(market="mkt1", client_id="c1"), _intent(market="mkt1"), "e1")
        mgr.add_order(_identity(market="mkt2", client_id="c2"), _intent(market="mkt2"), "e2")
        count = mgr.cancel_all(market_id="mkt1")
        assert count == 1

    def test_add_fill_and_get_fills(self):
        mgr = OrderManager()
        fill = FillEvent(
            fill_id="f1",
            market_id="mkt1",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.5,
            size=10.0,
            fee=0.01,
            timestamp=datetime(2026, 7, 4),
            source=FillSource.SIMULATED,
        )
        mgr.add_fill(fill)
        fills = mgr.get_fills()
        assert len(fills) == 1
        assert fills[0].fill_id == "f1"

    def test_get_fills_filtered(self):
        mgr = OrderManager()
        f1 = FillEvent(
            fill_id="f1",
            market_id="mkt1",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.5,
            size=10.0,
            fee=0.0,
            timestamp=datetime(2026, 7, 4),
            source=FillSource.SIMULATED,
        )
        f2 = FillEvent(
            fill_id="f2",
            market_id="mkt2",
            outcome="NO",
            side=OrderSide.SELL,
            price=0.6,
            size=5.0,
            fee=0.0,
            timestamp=datetime(2026, 7, 4),
            source=FillSource.SIMULATED,
        )
        mgr.add_fill(f1)
        mgr.add_fill(f2)
        fills = mgr.get_fills(market_id="mkt1")
        assert len(fills) == 1

    def test_get_position(self):
        mgr = OrderManager()
        f1 = FillEvent(
            fill_id="f1",
            market_id="mkt1",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.5,
            size=10.0,
            fee=0.0,
            timestamp=datetime(2026, 7, 4),
            source=FillSource.SIMULATED,
        )
        f2 = FillEvent(
            fill_id="f2",
            market_id="mkt1",
            outcome="YES",
            side=OrderSide.SELL,
            price=0.6,
            size=3.0,
            fee=0.0,
            timestamp=datetime(2026, 7, 4),
            source=FillSource.SIMULATED,
        )
        mgr.add_fill(f1)
        mgr.add_fill(f2)
        pos = mgr.get_position("mkt1", "YES")
        assert pos == 7.0  # 10 - 3

    def test_get_position_no_fills(self):
        mgr = OrderManager()
        assert mgr.get_position("mkt1", "YES") == 0.0

    def test_get_all_positions(self):
        mgr = OrderManager()
        mgr.add_fill(
            FillEvent(
                fill_id="f1",
                market_id="mkt1",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.5,
                size=10.0,
                fee=0.0,
                timestamp=datetime(2026, 7, 4),
                source=FillSource.SIMULATED,
            )
        )
        mgr.add_fill(
            FillEvent(
                fill_id="f2",
                market_id="mkt1",
                outcome="NO",
                side=OrderSide.BUY,
                price=0.4,
                size=20.0,
                fee=0.0,
                timestamp=datetime(2026, 7, 4),
                source=FillSource.SIMULATED,
            )
        )
        positions = mgr.get_all_positions()
        assert positions["mkt1"]["YES"] == 10.0
        assert positions["mkt1"]["NO"] == 20.0

    def test_summary(self):
        mgr = OrderManager()
        mgr.add_order(_identity(client_id="c1"), _intent(), "e1")
        mgr.add_order(_identity(client_id="c2"), _intent())
        mgr.update_status(_identity(client_id="c1").to_identity_string(), OrderStatus.FILLED)
        for i in range(3):
            mgr.add_fill(
                FillEvent(
                    fill_id=f"f{i}",
                    market_id="mkt1",
                    outcome="YES",
                    side=OrderSide.BUY,
                    price=0.5,
                    size=1.0,
                    fee=0.0,
                    timestamp=datetime(2026, 7, 4),
                    source=FillSource.SIMULATED,
                )
            )
        s = mgr.summary()
        assert s["total_orders"] == 2
        assert s["filled"] == 1
        assert s["open"] == 0  # c2 is PENDING, not yet OPEN
        assert s["total_fills"] == 3

    def test_update_status_with_exchange_id(self):
        """Line 108-109: update_status sets exchange_order_id."""
        mgr = OrderManager()
        mgr.add_order(_identity(client_id="c1"), _intent(), "exch1")
        key = _identity(client_id="c1").to_identity_string()
        updated = mgr.update_status(key, OrderStatus.PARTIALLY_FILLED, exchange_order_id="exch2")
        assert updated is not None
        assert updated.exchange_order_id == "exch2"

    def test_update_status_skips_zero_values(self):
        """Line 107: filled_value > 0 guard skips zero."""
        mgr = OrderManager()
        mgr.add_order(_identity(client_id="c1"), _intent(), "exch1")
        key = _identity(client_id="c1").to_identity_string()
        updated = mgr.update_status(key, OrderStatus.FILLED, filled_size=0, filled_value=0)
        assert updated is not None
        assert updated.filled_size == 0.0

    def test_update_status_with_filled_value(self):
        """Line 107: filled_value > 0 guard updates when positive."""
        mgr = OrderManager()
        mgr.add_order(_identity(client_id="c1"), _intent(), "exch1")
        key = _identity(client_id="c1").to_identity_string()
        updated = mgr.update_status(key, OrderStatus.FILLED, filled_size=5.0, filled_value=2.5)
        assert updated is not None
        assert updated.filled_value == 2.5

    def test_cancel_all_skips_non_open(self):
        """Line 154-155: cancel_all skips orders that are not OPEN/PARTIALLY_FILLED."""
        mgr = OrderManager()
        o1 = mgr.add_order(_identity(client_id="c1"), _intent(), "e1")
        mgr.update_status(_identity(client_id="c1").to_identity_string(), OrderStatus.FILLED)
        mgr.add_order(_identity(client_id="c2"), _intent(), "e2")
        count = mgr.cancel_all()
        # Only c2 was OPEN, c1 is FILLED
        assert count == 1
        assert mgr.get_order(o1.identity.to_identity_string()).status == OrderStatus.FILLED

    def test_cancel_all_with_market_filter_mismatch(self):
        """Line 156-157: cancel_all skips orders not matching market filter."""
        mgr = OrderManager()
        mgr.add_order(_identity(market="mkt1", client_id="c1"), _intent(market="mkt1"), "e1")
        mgr.add_order(_identity(market="mkt2", client_id="c2"), _intent(market="mkt2"), "e2")
        count = mgr.cancel_all(market_id="mkt3")
        assert count == 0

    def test_get_fills_unfiltered_returns_copy(self):
        """Line 171-172: get_fills without filter returns copy."""
        mgr = OrderManager()
        mgr.add_fill(
            FillEvent(
                fill_id="f1",
                market_id="mkt1",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.5,
                size=10.0,
                fee=0.0,
                timestamp=datetime(2026, 7, 4),
                source=FillSource.SIMULATED,
            )
        )
        fills = mgr.get_fills()
        assert len(fills) == 1

    def test_get_all_positions_empty(self):
        """No fills → empty dict."""
        mgr = OrderManager()
        assert mgr.get_all_positions() == {}

    def test_get_all_positions_sell_side(self):
        """Line 198-199: sell side decrements position."""
        mgr = OrderManager()
        mgr.add_fill(
            FillEvent(
                fill_id="f1",
                market_id="mkt1",
                outcome="YES",
                side=OrderSide.SELL,
                price=0.5,
                size=10.0,
                fee=0.0,
                timestamp=datetime(2026, 7, 4),
                source=FillSource.SIMULATED,
            )
        )
        positions = mgr.get_all_positions()
        assert positions["mkt1"]["YES"] == -10.0

    def test_summary_cancelled_count(self):
        """Line 213: cancelled count in summary."""
        mgr = OrderManager()
        mgr.add_order(_identity(client_id="c1"), _intent(), "e1")
        mgr.cancel_order(_identity(client_id="c1").to_identity_string())
        s = mgr.summary()
        assert s["cancelled"] == 1
