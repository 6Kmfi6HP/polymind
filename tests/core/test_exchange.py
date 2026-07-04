"""Tests for ExchangeAdapter interface."""

from __future__ import annotations

from datetime import datetime

from polymind.core.exchange import (
    ExchangeAdapter,
    MarketInfo,
    OrderBook,
    OrderBookLevel,
    OrderResult,
    Position,
)


class TestDomainTypes:
    def test_market_info_defaults(self):
        mi = MarketInfo(market_id="0x1", title="Test")
        assert mi.status == "active"

    def test_order_book_level(self):
        obl = OrderBookLevel(price=0.5, size=100.0)
        assert obl.price == 0.5

    def test_order_book(self):
        ts = datetime(2026, 1, 1)
        ob = OrderBook(
            market_id="m1",
            bids=[OrderBookLevel(0.4, 50)],
            asks=[OrderBookLevel(0.6, 50)],
            timestamp=ts,
        )
        assert len(ob.bids) == 1
        assert len(ob.asks) == 1

    def test_order_result_defaults(self):
        or_ = OrderResult(
            order_id="o1", status="open", market_id="m1", side="buy", price=0.5, size=10
        )
        assert or_.filled_size == 0.0
        assert or_.error is None

    def test_position(self):
        p = Position(market_id="m1", side="long", size=100.0, entry_price=0.5)
        assert p.unrealized_pnl == 0.0


class TestExchangeAdapter:
    def test_cannot_instantiate(self):
        """ABC cannot be instantiated directly."""
        import pytest

        with pytest.raises(TypeError):
            ExchangeAdapter()  # type: ignore[abstract]

    def test_concrete_subclass(self):
        """A minimal subclass can be instantiated and has abstract methods."""

        class MockAdapter(ExchangeAdapter):
            @property
            def name(self) -> str:
                return "mock"

            @property
            def connected(self) -> bool:
                return True

            async def connect(self):
                pass

            async def close(self):
                pass

            async def get_markets(self, active=True, limit=50):
                return []

            async def get_order_book(self, market_id):
                return None

            async def place_order(self, market_id, side, price, size, **kwargs):
                return OrderResult(
                    order_id="mock",
                    status="open",
                    market_id=market_id,
                    side=side,
                    price=price,
                    size=size,
                )

            async def cancel_order(self, order_id):
                return True

            async def cancel_all_orders(self, market_id=None):
                return 0

            async def get_positions(self):
                return []

            async def get_balance(self):
                return 0.0

        adapter = MockAdapter()
        assert adapter.name == "mock"
        assert adapter.connected is True
