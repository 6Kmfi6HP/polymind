"""
Tests for the real Polymarket CLOB client wrapper.

All SDK calls are synchronous and run through asyncio.to_thread, so we
patch ClobClient directly and use MagicMock for the SDK instances.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polymind.polymarket.client import (
    MarketSummary,
    OrderBookSnapshot,
    OrderResult,
    PolymarketClient,
)
from polymind.polymarket.errors import (
    MarketNotFoundError,
    PolymarketError,
)
from polymind.polymarket.signer import Signer

# ---------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def mock_sdk():
    """Patch ClobClient and return a fresh MagicMock for its constructor."""
    with patch("polymind.polymarket.client.ClobClient") as m:
        instance = MagicMock()
        m.return_value = instance
        yield instance


@pytest.fixture
def sample_market_data():
    return {
        "condition_id": "0xabc",
        "question": "Test market?",
        "active": True,
        "closed": False,
        "neg_risk": False,
        "minimum_tick_size": 0.01,
        "minimum_order_size": 5,
        "accepting_orders": True,
        "accepting_order_timestamp": "2025-01-01T00:00:00Z",
        "tokens": [
            {
                "token_id": "111",
                "outcome": "Yes",
                "price": "0.55",
            },
            {
                "token_id": "222",
                "outcome": "No",
                "price": "0.45",
            },
        ],
    }


@pytest.fixture
def sample_orderbook():
    from py_clob_client.clob_types import OrderBookSummary, OrderSummary

    return OrderBookSummary(
        market="0xabc",
        asset_id="111",
        timestamp="1700000000",
        bids=[OrderSummary(price="0.50", size="100")],
        asks=[OrderSummary(price="0.60", size="200")],
        min_order_size="5",
        neg_risk=False,
        tick_size="0.01",
        last_trade_price="0.55",
        hash="0x",
    )


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_public(self, mock_sdk):
        """Public-tier signer creates an unauthenticated ClobClient."""
        from polymind.polymarket import client as client_mod

        client = PolymarketClient(signer=Signer.public())
        await client.connect()

        client_mod.ClobClient.assert_called_once_with(
            host="https://clob.polymarket.com",
            chain_id=137,
        )
        assert client._client is not None

    @pytest.mark.asyncio
    async def test_connect_wallet(self, mock_sdk):
        """Wallet-tier signer passes private_key to ClobClient."""
        from polymind.polymarket import client as client_mod

        client = PolymarketClient(signer=Signer.from_wallet("0xdeadbeef"))
        await client.connect()

        client_mod.ClobClient.assert_called_once_with(
            host="https://clob.polymarket.com",
            chain_id=137,
            key="0xdeadbeef",
        )

    @pytest.mark.asyncio
    async def test_connect_api_key(self, mock_sdk):
        """API-key signer sets creds after constructing ClobClient."""
        from polymind.polymarket import client as client_mod

        client = PolymarketClient(signer=Signer.from_api_key("ak_1", "secret", "phrase"))
        await client.connect()

        client_mod.ClobClient.assert_called_once_with(
            host="https://clob.polymarket.com",
            chain_id=137,
        )
        mock_sdk.set_api_creds.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, mock_sdk):
        """Calling connect() twice only creates one SDK client."""
        from polymind.polymarket import client as client_mod

        client = PolymarketClient(signer=Signer.public())
        await client.connect()
        await client.connect()

        client_mod.ClobClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_no_signer(self, mock_sdk):
        """No signer creates an unauthenticated client."""
        from polymind.polymarket import client as client_mod

        client = PolymarketClient()
        await client.connect()

        client_mod.ClobClient.assert_called_once_with(
            host="https://clob.polymarket.com",
            chain_id=137,
        )

    @pytest.mark.asyncio
    async def test_connect_chain_id_resolution(self):
        """Staging host resolves to chain_id 80001."""
        with patch("polymind.polymarket.client.ClobClient") as m:
            instance = MagicMock()
            m.return_value = instance
            client = PolymarketClient(
                host="https://staging.clob.polymarket.com",
                signer=Signer.public(),
            )
            await client.connect()
            m.assert_called_once_with(
                host="https://staging.clob.polymarket.com",
                chain_id=80001,
            )


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------


class TestGetMarkets:
    @pytest.mark.asyncio
    async def test_returns_list_of_market_summaries(self, mock_sdk, sample_market_data):
        """get_markets() returns MarketSummary objects from SDK data."""
        mock_sdk.get_markets.return_value = {"data": [sample_market_data]}

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_markets()

        assert len(result) == 2
        assert all(isinstance(m, MarketSummary) for m in result)
        assert result[0].condition_id == "0xabc"
        assert result[0].token_id == "111"
        assert result[0].outcome == "Yes"
        assert result[0].price == 0.55
        assert result[1].price == 0.45

    @pytest.mark.asyncio
    async def test_active_filter(self, mock_sdk, sample_market_data):
        """active=True filters out inactive markets."""
        inactive = dict(sample_market_data, active=False)
        mock_sdk.get_markets.return_value = {"data": [sample_market_data, inactive]}

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_markets()

        assert len(result) == 2  # both tokens from active market

    @pytest.mark.asyncio
    async def test_limit(self, mock_sdk, sample_market_data):
        """limit parameter caps the returned market count."""
        # Generate many tokens
        market = dict(sample_market_data)
        market["tokens"] = [
            {"token_id": str(i), "outcome": f"O{i}", "price": "0.5"} for i in range(100)
        ]
        mock_sdk.get_markets.return_value = {"data": [market]}

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_markets(limit=10)

        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_handles_raw_list_response(self, mock_sdk, sample_market_data):
        """get_markets handles both dict and raw list responses."""
        mock_sdk.get_markets.return_value = [sample_market_data]

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_markets()

        assert len(result) == 2


class TestGetMarket:
    @pytest.mark.asyncio
    async def test_returns_summary(self, mock_sdk, sample_market_data):
        mock_sdk.get_market.return_value = sample_market_data

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_market("0xabc")

        assert result is not None
        assert isinstance(result, MarketSummary)
        assert result.condition_id == "0xabc"

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.get_market.side_effect = PolyApiException(error_msg='{"error": "not found"}')
        mock_sdk.get_market.side_effect.status_code = 404

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_market("0xmissing")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_response(self, mock_sdk):
        mock_sdk.get_market.return_value = None

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_market("0xabc")

        assert result is None


# ---------------------------------------------------------------------------
# Order book
# ---------------------------------------------------------------------------


class TestGetOrderBook:
    @pytest.mark.asyncio
    async def test_returns_snapshot(self, mock_sdk, sample_orderbook):
        mock_sdk.get_order_book.return_value = sample_orderbook

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_order_book("111")

        assert result is not None
        assert isinstance(result, OrderBookSnapshot)
        assert result.market_id == "0xabc"
        assert result.token_id == "111"
        assert result.tick_size == 0.01
        assert len(result.bids) == 1
        assert result.bids[0].price == 0.50
        assert result.bids[0].size == 100
        assert len(result.asks) == 1
        assert result.asks[0].price == 0.60

    @pytest.mark.asyncio
    async def test_returns_none_on_missing_book(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.get_order_book.side_effect = PolyApiException(error_msg='{"error": "no book"}')
        mock_sdk.get_order_book.side_effect.status_code = 404

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_order_book("111")

        assert result is None


class TestGetMidpoint:
    @pytest.mark.asyncio
    async def test_returns_float(self, mock_sdk):
        mock_sdk.get_midpoint.return_value = 0.55

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_midpoint("111")

        assert result == 0.55

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.get_midpoint.side_effect = PolyApiException(error_msg="error")
        mock_sdk.get_midpoint.side_effect.status_code = 404

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_midpoint("111")

        assert result == 0.0


class TestGetSpread:
    @pytest.mark.asyncio
    async def test_returns_float(self, mock_sdk):
        mock_sdk.get_spread.return_value = 0.05

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_spread("111")

        assert result == 0.05

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.get_spread.side_effect = PolyApiException(error_msg="error")
        mock_sdk.get_spread.side_effect.status_code = 404

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_spread("111")

        assert result == 0.0


class TestGetLastTradePrice:
    @pytest.mark.asyncio
    async def test_returns_float(self, mock_sdk):
        mock_sdk.get_last_trade_price.return_value = 0.55

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_last_trade_price("111")

        assert result == 0.55

    @pytest.mark.asyncio
    async def test_handles_dict_response(self, mock_sdk):
        mock_sdk.get_last_trade_price.return_value = {"price": "0.55", "side": "SELL"}

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_last_trade_price("111")

        assert result == 0.55

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.get_last_trade_price.side_effect = PolyApiException(error_msg="error")
        mock_sdk.get_last_trade_price.side_effect.status_code = 404

        client = PolymarketClient(signer=Signer.public())
        result = await client.get_last_trade_price("111")

        assert result == 0.0


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


class TestPlaceOrder:
    @pytest.mark.asyncio
    async def test_creates_and_posts_order(self, mock_sdk):
        mock_sdk.create_order.return_value = MagicMock()
        mock_sdk.post_order.return_value = {"success": True, "order_id": "ord-1"}

        client = PolymarketClient(signer=Signer.from_wallet("0xdeadbeef"))
        result = await client.place_order(token_id="111", price=0.5, size=100, side="BUY")

        assert result == {"success": True, "order_id": "ord-1"}
        mock_sdk.create_order.assert_called_once()
        mock_sdk.post_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.create_order.side_effect = PolyApiException(error_msg="error")
        mock_sdk.create_order.side_effect.status_code = 400

        client = PolymarketClient(signer=Signer.from_wallet("0xdeadbeef"))
        result = await client.place_order(token_id="111", price=0.5, size=100, side="BUY")

        assert result is None


class TestCancelOrder:
    @pytest.mark.asyncio
    async def test_cancel_returns_true(self, mock_sdk):
        mock_sdk.cancel.return_value = {"success": True}

        client = PolymarketClient(signer=Signer.from_wallet("0xdeadbeef"))
        result = await client.cancel_order("ord-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_returns_false_on_error(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.cancel.side_effect = PolyApiException(error_msg="error")
        mock_sdk.cancel.side_effect.status_code = 400

        client = PolymarketClient(signer=Signer.from_wallet("0xdeadbeef"))
        result = await client.cancel_order("ord-1")

        assert result is False


class TestCancelAllOrders:
    @pytest.mark.asyncio
    async def test_cancel_all_returns_true(self, mock_sdk):
        mock_sdk.cancel_all.return_value = {"success": True}

        client = PolymarketClient(signer=Signer.from_wallet("0xdeadbeef"))
        result = await client.cancel_all_orders()

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_all_returns_false_on_error(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.cancel_all.side_effect = PolyApiException(error_msg="error")
        mock_sdk.cancel_all.side_effect.status_code = 400

        client = PolymarketClient(signer=Signer.from_wallet("0xdeadbeef"))
        result = await client.cancel_all_orders()

        assert result is False


class TestGetOrders:
    @pytest.mark.asyncio
    async def test_returns_order_list(self, mock_sdk):
        mock_sdk.get_orders.return_value = [
            {
                "id": "ord-1",
                "status": "OPEN",
                "market": "0xabc",
                "side": "BUY",
                "price": "0.50",
                "size": "100",
                "filled_size": "0",
                "remaining_size": "100",
                "created_at": "2025-01-01T00:00:00Z",
            }
        ]

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        result = await client.get_orders()

        assert len(result) == 1
        assert isinstance(result[0], OrderResult)
        assert result[0].order_id == "ord-1"
        assert result[0].status == "OPEN"

    @pytest.mark.asyncio
    async def test_filters_with_params(self, mock_sdk):
        mock_sdk.get_orders.return_value = []

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        await client.get_orders(params={"market": "0xabc"})

        mock_sdk.get_orders.assert_called_once()
        call_args = mock_sdk.get_orders.call_args[0][0]
        assert call_args.market == "0xabc"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.get_orders.side_effect = PolyApiException(error_msg="error")
        mock_sdk.get_orders.side_effect.status_code = 401

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        result = await client.get_orders()

        assert result == []


class TestGetOrder:
    @pytest.mark.asyncio
    async def test_returns_order_result(self, mock_sdk):
        mock_sdk.get_order.return_value = {
            "id": "ord-1",
            "status": "OPEN",
            "market": "0xabc",
            "side": "BUY",
            "price": "0.50",
            "size": "100",
            "filled_size": "0",
            "remaining_size": "100",
            "created_at": "2025-01-01T00:00:00Z",
        }

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        result = await client.get_order("ord-1")

        assert result is not None
        assert isinstance(result, OrderResult)
        assert result.order_id == "ord-1"

    @pytest.mark.asyncio
    async def test_returns_none_on_404(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.get_order.side_effect = PolyApiException(error_msg="not found")
        mock_sdk.get_order.side_effect.status_code = 404

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        result = await client.get_order("ord-missing")

        assert result is None


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


class TestGetPositions:
    @pytest.mark.asyncio
    async def test_returns_empty(self, mock_sdk):
        client = PolymarketClient(signer=Signer.public())
        result = await client.get_positions()
        assert result == []


class TestGetBalance:
    @pytest.mark.asyncio
    async def test_returns_float(self, mock_sdk):
        mock_sdk.get_balance_allowance.return_value = {"balance": "1000.50"}

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        result = await client.get_balance()

        assert result == 1000.50

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.get_balance_allowance.side_effect = PolyApiException(error_msg="err")
        mock_sdk.get_balance_allowance.side_effect.status_code = 401

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        result = await client.get_balance()

        assert result == 0.0


class TestGetFills:
    @pytest.mark.asyncio
    async def test_returns_fill_events(self, mock_sdk):
        mock_sdk.get_trades.return_value = [
            {
                "id": "fill-1",
                "side": "BUY",
                "price": "0.55",
                "size": "100",
                "fee": "0.1",
                "outcome": "Yes",
                "timestamp": "2025-01-01T00:00:00Z",
                "order_id": "ord-1",
            }
        ]

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        result = await client.get_fills(market_id="0xabc")

        assert len(result) == 1
        assert result[0].fill_id == "fill-1"
        assert result[0].price == 0.55
        assert result[0].size == 100

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, mock_sdk):
        from py_clob_client.exceptions import PolyApiException

        mock_sdk.get_trades.side_effect = PolyApiException(error_msg="error")
        mock_sdk.get_trades.side_effect.status_code = 401

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        result = await client.get_fills(market_id="0xabc")

        assert result == []


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


class TestErrorMapping:
    @pytest.mark.asyncio
    async def test_404_maps_to_market_not_found(self, mock_sdk):
        """SDK 404 from _run raises MarketNotFoundError."""
        from py_clob_client.exceptions import PolyApiException

        exc = PolyApiException(error_msg="not found")
        exc.status_code = 404
        mock_sdk.get_midpoint.side_effect = exc

        client = PolymarketClient(signer=Signer.public())
        await client.connect()
        with pytest.raises(MarketNotFoundError):
            await client._run("get_midpoint", "111")

    @pytest.mark.asyncio
    async def test_generic_poly_exception_maps(self, mock_sdk):
        """SDK non-404 PolyApiException raises PolymarketError."""
        from py_clob_client.exceptions import PolyApiException

        exc = PolyApiException(error_msg="oops")
        exc.status_code = 500
        mock_sdk.get_midpoint.side_effect = exc

        client = PolymarketClient(signer=Signer.public())
        await client.connect()
        with pytest.raises(PolymarketError):
            await client._run("get_midpoint", "111")


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------


class TestClose:
    @pytest.mark.asyncio
    async def test_close_sets_client_to_none(self, mock_sdk):
        client = PolymarketClient(signer=Signer.public())
        await client.connect()
        assert client._client is not None
        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self, mock_sdk):
        client = PolymarketClient(signer=Signer.public())
        await client.close()
        # No error on double close
        await client.close()


# ---------------------------------------------------------------------------
# Lazy connection (_run auto-connects)
# ---------------------------------------------------------------------------


class TestLazyConnection:
    @pytest.mark.asyncio
    async def test_get_markets_auto_connects(self):
        """Calling get_markets without explicit connect() works."""
        with patch("polymind.polymarket.client.ClobClient") as m:
            instance = MagicMock()
            instance.get_markets.return_value = {"data": []}
            m.return_value = instance

            client = PolymarketClient(signer=Signer.public())
            result = await client.get_markets()

            assert result == []
            m.assert_called_once()


# ---------------------------------------------------------------------------
# Edge coverage for uncovered lines
# ---------------------------------------------------------------------------


class TestEdgeCoverage:
    """Target gap lines: 124, 205, 295, 377, 475, 477, 479, 481, 510, 551, 553, 555."""

    @pytest.mark.asyncio
    async def test_connect_double_checked_lock(self, mock_sdk):
        """Line 124: second connection check inside the lock."""
        client = PolymarketClient(signer=Signer.public())
        # Acquire the lock externally so connect() enters the lock block
        # but _client is already set when the inner check runs.
        await client._lock.acquire()
        client._client = MagicMock()
        client._lock.release()
        await client.connect()
        assert client._client is not None

    @pytest.mark.asyncio
    async def test_order_book_empty_response(self, mock_sdk):
        """Line 205: get_order_book returns None when SDK returns falsy book."""
        mock_sdk.get_order_book.return_value = None

        client = PolymarketClient(signer=Signer.public())
        await client.connect()
        result = await client.get_order_book("111")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_order_empty_data(self, mock_sdk):
        """Line 295: get_order returns None when SDK returns falsy data."""
        mock_sdk.get_order.return_value = None

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        await client.connect()
        result = await client.get_order("ord-missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_balance_non_dict_response(self, mock_sdk):
        """Line 377: balance allowance returns non-dict."""
        mock_sdk.get_balance_allowance.return_value = "not_a_dict"

        client = PolymarketClient(signer=Signer.from_api_key("a", "b", "c"))
        await client.connect()
        result = await client.get_balance()
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_run_rate_limit_error(self, mock_sdk):
        """Line 475: 429 status raises RateLimitError."""
        from py_clob_client.exceptions import PolyApiException

        exc = PolyApiException(error_msg="rate limited")
        exc.status_code = 429
        mock_sdk.get_midpoint.side_effect = exc

        client = PolymarketClient(signer=Signer.public())
        await client.connect()
        from polymind.polymarket.errors import RateLimitError

        with pytest.raises(RateLimitError):
            await client._run("get_midpoint", "111")

    @pytest.mark.asyncio
    async def test_run_poly_exception(self, mock_sdk):
        """Line 477-478: PolyException wraps to PolymarketError."""
        from py_clob_client.exceptions import PolyException

        mock_sdk.get_midpoint.side_effect = PolyException("poly error")

        client = PolymarketClient(signer=Signer.public())
        await client.connect()

        with pytest.raises(PolymarketError):
            await client._run("get_midpoint", "111")

    @pytest.mark.asyncio
    async def test_run_connection_error_mapped(self, mock_sdk):
        """Line 479-482: ConnectionError maps to ConnectionError."""
        from polymind.polymarket.errors import ConnectionError as PolymarketConnectionError

        mock_sdk.get_midpoint.side_effect = ConnectionError("connect failed")

        client = PolymarketClient(signer=Signer.public())
        await client.connect()

        with pytest.raises(PolymarketConnectionError):
            await client._run("get_midpoint", "111")

    @pytest.mark.asyncio
    async def test_run_generic_exception(self, mock_sdk):
        """Line 483: generic Exception maps to PolymarketError."""
        mock_sdk.get_midpoint.side_effect = ValueError("weird")

        client = PolymarketClient(signer=Signer.public())
        await client.connect()

        with pytest.raises(PolymarketError):
            await client._run("get_midpoint", "111")

    @pytest.mark.asyncio
    async def test_parse_market_no_tokens(self, mock_sdk):
        """Line 510-521: market without tokens list."""
        client = PolymarketClient(signer=Signer.public())
        data = {
            "condition_id": "0xabc",
            "closed": False,
            "neg_risk": True,
            "minimum_tick_size": 0.01,
            "minimum_order_size": 1,
            "token_id": "111",
            "outcome": "Yes",
            "price": "0.55",
        }
        result = client._parse_market(data)
        assert result.condition_id == "0xabc"
        assert result.token_id == "111"
        assert result.neg_risk is True

    def test_parse_timestamp_none(self):
        """Line 551: _parse_timestamp(None) returns None."""
        from polymind.polymarket.client import _parse_timestamp

        assert _parse_timestamp(None) is None

    def test_parse_timestamp_datetime(self):
        """Line 553: _parse_timestamp(datetime) returns as-is."""
        from datetime import datetime as dt

        from polymind.polymarket.client import _parse_timestamp

        now = dt.now()
        assert _parse_timestamp(now) is now

    def test_parse_timestamp_int(self):
        """Line 555: _parse_timestamp(int) converts from epoch."""
        from polymind.polymarket.client import _parse_timestamp

        result = _parse_timestamp(1700000000)
        assert result is not None
        assert result.year == 2023
