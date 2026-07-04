"""Tests for ExchangeAdapter interface."""

from __future__ import annotations

from datetime import datetime

import pytest

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

    @pytest.mark.asyncio
    async def test_abstract_methods_ellipsis_body(self):
        """Class-dispatch to ExchangeAdapter hits each abstract ellipsis body (lines 81-143)."""

        class _Minimal(ExchangeAdapter):
            @property
            def name(self) -> str:
                return "min"

            @property
            def connected(self) -> bool:
                return False

            async def connect(self):
                return await ExchangeAdapter.connect(self)

            async def close(self):
                return await ExchangeAdapter.close(self)

            async def get_markets(self, active: bool = True, limit: int = 50):
                return await ExchangeAdapter.get_markets(self, active, limit)

            async def get_order_book(self, market_id: str):
                return await ExchangeAdapter.get_order_book(self, market_id)

            async def place_order(self, market_id, side, price, size, **kwargs):
                return await ExchangeAdapter.place_order(
                    self, market_id, side, price, size, **kwargs
                )

            async def cancel_order(self, order_id):
                return await ExchangeAdapter.cancel_order(self, order_id)

            async def cancel_all_orders(self, market_id=None):
                return await ExchangeAdapter.cancel_all_orders(self, market_id)

            async def get_positions(self):
                return await ExchangeAdapter.get_positions(self)

            async def get_balance(self):
                return await ExchangeAdapter.get_balance(self)

        a = _Minimal()

        # connect / close
        assert await a.connect() is None
        assert await a.close() is None

        # market data
        markets = await a.get_markets()
        assert markets is None
        ob = await a.get_order_book("x")
        assert ob is None

        # trading
        result = await a.place_order("x", "buy", 1.0, 10)
        assert result is None
        assert await a.cancel_order("o") is None
        assert await a.cancel_all_orders() is None

        # account
        assert await a.get_positions() is None
        assert await a.get_balance() is None

        # properties — class-dispatch via .fget to cover abstract body lines
        assert ExchangeAdapter.name.fget(a) is None
        assert ExchangeAdapter.connected.fget(a) is None
