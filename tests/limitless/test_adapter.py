"""
Tests for Limitless exchange adapter — mock-based HTTP + SDK.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from polymind.limitless.adapter import LimitlessAdapter, LimitlessConfig

# Mock SDK enums for tests that exercise the SDK path
_MockSide = MagicMock()
_MockSide.BUY = "BUY"
_MockSide.SELL = "SELL"

_MockOrderType = MagicMock()
_MockOrderType.GTC = "GTC"
_MockOrderType.FAK = "FAK"
_MockOrderType.FOK = "FOK"


@pytest.fixture
def adapter() -> LimitlessAdapter:
    cfg = LimitlessConfig(api_key="test-key-123")
    return LimitlessAdapter(config=cfg)


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.delete = AsyncMock()
    client.aclose = AsyncMock()
    return client


class TestLimitlessConfig:
    def test_defaults(self):
        cfg = LimitlessConfig()
        assert cfg.base_url == "https://api.limitless.exchange"
        assert cfg.api_key == ""

    def test_env_var_fallback(self):
        with patch.dict("os.environ", {"LIMITLESS_API_KEY": "env-key"}):
            cfg = LimitlessConfig()
            assert cfg.api_key == "env-key"

    def test_explicit_overrides_env(self):
        with patch.dict("os.environ", {"LIMITLESS_API_KEY": "env-key"}):
            cfg = LimitlessConfig(api_key="explicit")
            assert cfg.api_key == "explicit"

    def test_private_key_env(self):
        with patch.dict("os.environ", {"LIMITLESS_PRIVATE_KEY": "0xabc"}):
            cfg = LimitlessConfig()
            assert cfg.private_key == "0xabc"


class TestLimitlessAdapterProperties:
    def test_name(self, adapter: LimitlessAdapter):
        assert adapter.name == "limitless"

    def test_connected_default(self, adapter: LimitlessAdapter):
        assert adapter.connected is False

    async def test_connected_after_connect(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.post = AsyncMock()
        mock_http.delete = AsyncMock()
        mock_http.aclose = AsyncMock()
        with patch("httpx.AsyncClient", return_value=mock_http):
            await adapter.connect()
            assert adapter.connected is True

    async def test_close(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.aclose = AsyncMock()
        adapter._client = mock_http
        await adapter.close()
        assert adapter._client is None


class TestLimitlessAdapterConnect:
    async def test_connect_creates_client(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.post = AsyncMock()
        mock_http.delete = AsyncMock()
        mock_http.aclose = AsyncMock()
        with patch("httpx.AsyncClient", return_value=mock_http) as mock_cls:
            await adapter.connect()
            mock_cls.assert_called_once()
            assert adapter._client is not None

    async def test_connect_with_private_key_tries_sdk(self, adapter: LimitlessAdapter):
        """With private_key, connect should try to init OrderClient."""
        adapter._config.private_key = "0x" + "ab" * 32
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.post = AsyncMock()
        mock_http.delete = AsyncMock()
        mock_http.aclose = AsyncMock()
        with (
            patch("httpx.AsyncClient", return_value=mock_http),
            patch(
                "polymind.limitless.adapter.LimitlessAdapter._try_init_order_client"
            ) as mock_init,
        ):
            mock_init.return_value = MagicMock()
            await adapter.connect()
            mock_init.assert_called_once()
            assert adapter._order_client is not None

    async def test_connect_with_private_key_no_sdk(self, adapter: LimitlessAdapter):
        """With private_key but no limitless_sdk, OrderClient stays None."""
        adapter._config.private_key = "0x" + "ab" * 32
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.post = AsyncMock()
        mock_http.delete = AsyncMock()
        mock_http.aclose = AsyncMock()
        with patch("httpx.AsyncClient", return_value=mock_http):
            await adapter.connect()
            # _try_init_order_client will fail ImportError silently
            assert adapter._order_client is None


class TestLimitlessAdapterMarkets:
    async def test_get_markets(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={
                "data": [
                    {"slug": "btc-2024", "title": "Bitcoin 2024", "status": "active"},
                    {"slug": "eth-2024", "title": "Ethereum 2024", "status": "active"},
                ],
            },
        )
        adapter._client = mock_http

        markets = await adapter.get_markets()
        assert len(markets) == 2
        assert markets[0].market_id == "btc-2024"
        assert markets[0].title == "Bitcoin 2024"
        assert markets[1].market_id == "eth-2024"

    async def test_get_markets_with_token_outcomes(self, adapter: LimitlessAdapter):
        """Markets with tokens.yes/.no get YES/NO outcomes."""
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={
                "data": [
                    {
                        "slug": "btc-2024",
                        "title": "Bitcoin 2024",
                        "tokens": {"yes": "0xyes", "no": "0xno"},
                    },
                ],
            },
        )
        adapter._client = mock_http

        markets = await adapter.get_markets()
        assert markets[0].outcomes == ["YES", "NO"]

    async def test_get_markets_without_connect(self, adapter: LimitlessAdapter):
        with pytest.raises(RuntimeError, match="Not connected"):
            await adapter.get_markets()

    async def test_get_market_found(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={"slug": "btc-2024", "title": "Bitcoin 2024", "status": "active"},
        )
        adapter._client = mock_http

        market = await adapter.get_market("btc-2024")
        assert market is not None
        assert market.market_id == "btc-2024"
        assert market.title == "Bitcoin 2024"

    async def test_get_market_not_found(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=404)
        adapter._client = mock_http

        market = await adapter.get_market("nonexistent")
        assert market is None

    async def test_get_order_book(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={
                "bids": [{"price": 0.45, "size": 1000}],
                "asks": [{"price": 0.55, "size": 2000}],
                "adjustedMidpoint": 0.50,
            },
        )
        adapter._client = mock_http

        ob = await adapter.get_order_book("btc-2024")
        assert ob is not None
        assert len(ob.bids) == 1
        assert ob.bids[0].price == 0.45
        assert ob.asks[0].size == 2000.0
        assert ob.market_id == "btc-2024"

    async def test_get_order_book_not_found(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=404)
        adapter._client = mock_http

        ob = await adapter.get_order_book("nonexistent")
        assert ob is None

    async def test_get_order_book_amm_market(self, adapter: LimitlessAdapter):
        """AMM markets return 400; return None."""
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=400)
        adapter._client = mock_http

        ob = await adapter.get_order_book("amm-market")
        assert ob is None


class TestLimitlessAdapterTrading:
    async def test_cancel_order(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.delete = AsyncMock()
        mock_http.delete.return_value = MagicMock(status_code=200)
        adapter._client = mock_http

        assert await adapter.cancel_order("ord-123") is True

    async def test_cancel_order_failure(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.delete = AsyncMock()
        mock_http.delete.return_value = MagicMock(status_code=400)
        adapter._client = mock_http

        assert await adapter.cancel_order("ord-123") is False

    async def test_cancel_all_orders_no_market(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock()
        mock_http.post.return_value = MagicMock(status_code=200)
        mock_http.post.return_value.json = MagicMock(
            return_value={"cancelled": ["ord1", "ord2"]},
        )
        adapter._client = mock_http

        count = await adapter.cancel_all_orders()
        assert count == 2

    async def test_cancel_all_orders_with_market(self, adapter: LimitlessAdapter):
        """With market_id and no SDK client, falls back to REST call."""
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.delete = AsyncMock()
        mock_http.delete.return_value = MagicMock(status_code=200)
        mock_http.delete.return_value.json = MagicMock(
            return_value={"cancelled": ["ord1"]},
        )
        adapter._client = mock_http
        adapter._order_client = None

        count = await adapter.cancel_all_orders(market_id="btc-2024")
        assert count == 1

    async def test_cancel_all_orders_with_sdk(self, adapter: LimitlessAdapter):
        """With market_id and SDK client, delegates to SDK."""
        mock_order_client = MagicMock()
        mock_order_client.cancel_all = AsyncMock()
        adapter._order_client = mock_order_client
        mock_http = MagicMock(spec=httpx.AsyncClient)
        adapter._client = mock_http

        count = await adapter.cancel_all_orders(market_id="btc-2024")
        assert count == -1  # SDK path returns -1
        mock_order_client.cancel_all.assert_called_once_with("btc-2024")

    async def test_cancel_all_orders_without_connect_raises(self, adapter: LimitlessAdapter):
        with pytest.raises(RuntimeError, match="Not connected"):
            await adapter.cancel_all_orders()

    async def test_place_order_no_sdk_raises(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        adapter._client = mock_http
        adapter._order_client = None

        with pytest.raises(RuntimeError, match="limitless-sdk"):
            await adapter.place_order("btc-2024", "BUY", 0.50, 100)

    async def test_place_order_success(self, adapter: LimitlessAdapter):
        """SDK path — successful order."""
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={"slug": "btc-2024", "tokens": {"yes": "0xyes"}},
        )
        adapter._client = mock_http

        mock_order = MagicMock()
        mock_order.order = {"id": "ord-new", "status": "open", "filled_size": 0}
        mock_order_client = MagicMock()
        mock_order_client.create_order = AsyncMock(return_value=mock_order)
        adapter._order_client = mock_order_client
        adapter._market_fetcher = MagicMock()
        adapter._market_fetcher.get_market = AsyncMock()

        with patch.object(
            adapter,
            "_get_sdk_enums",
            return_value=(_MockSide, _MockOrderType, _MockOrderType),
        ):
            result = await adapter.place_order(
                "btc-2024",
                "BUY",
                0.50,
                100,
                order_type="GTC",
            )
        assert result.order_id == "ord-new"
        assert result.status == "open"
        assert result.price == 0.50

    async def test_place_order_sdk_exception(self, adapter: LimitlessAdapter):
        """SDK raises exception -> OrderResult with error."""
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={"slug": "btc-2024", "tokens": {"yes": "0xyes"}},
        )
        adapter._client = mock_http

        mock_order_client = MagicMock()
        mock_order_client.create_order = AsyncMock(side_effect=ValueError("bad order"))
        adapter._order_client = mock_order_client
        adapter._market_fetcher = MagicMock()
        adapter._market_fetcher.get_market = AsyncMock()

        with patch.object(
            adapter,
            "_get_sdk_enums",
            return_value=(_MockSide, _MockOrderType, _MockOrderType),
        ):
            result = await adapter.place_order("btc-2024", "BUY", 0.50, 100)
        assert result.status == "failed"
        assert "bad order" in result.error

    async def test_cancel_all_orders_failure(self, adapter: LimitlessAdapter):
        """cancel_all_orders with non-200 response returns 0."""
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock()
        mock_http.post.return_value = MagicMock(status_code=500)
        adapter._client = mock_http

        count = await adapter.cancel_all_orders()
        assert count == 0

    async def test_cancel_all_orders_sdk_exception(self, adapter: LimitlessAdapter):
        """SDK client raises -> falls through to REST."""
        mock_order_client = MagicMock()
        mock_order_client.cancel_all = AsyncMock(side_effect=ValueError("SDK error"))
        adapter._order_client = mock_order_client

        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.delete = AsyncMock()
        mock_http.delete.return_value = MagicMock(status_code=200)
        mock_http.delete.return_value.json = MagicMock(
            return_value={"cancelled": ["ord1"]},
        )
        adapter._client = mock_http

        count = await adapter.cancel_all_orders(market_id="btc-2024")
        assert count == 1

    async def test_place_order_market_fetcher_raises(
        self,
        adapter: LimitlessAdapter,
    ):
        """place_order with market_fetcher that raises falls through."""
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={"slug": "btc-2024", "tokens": {"yes": "0xyes"}},
        )
        adapter._client = mock_http

        mock_order = MagicMock()
        mock_order.order = {"id": "ord-1", "status": "open", "filled_size": 0}
        mock_order_client = MagicMock()
        mock_order_client.create_order = AsyncMock(return_value=mock_order)
        adapter._order_client = mock_order_client

        mock_mf = MagicMock()
        mock_mf.get_market = AsyncMock(side_effect=ValueError("cache fail"))
        adapter._market_fetcher = mock_mf

        with patch.object(
            adapter,
            "_get_sdk_enums",
            return_value=(_MockSide, _MockOrderType, _MockOrderType),
        ):
            result = await adapter.place_order("btc-2024", "BUY", 0.50, 100)
        assert result.order_id == "ord-1"


class TestLimitlessAdapterPortfolio:
    async def test_get_positions(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={
                "clob": [
                    {"slug": "btc-2024", "shares": 100, "avgPrice": 0.65, "unrealizedPnl": 5.0},
                    {"slug": "eth-2024", "shares": -50, "avgPrice": 0.30, "unrealizedPnl": -2.0},
                ],
            },
        )
        adapter._client = mock_http

        positions = await adapter.get_positions()
        assert len(positions) == 2
        assert positions[0].market_id == "btc-2024"
        assert positions[0].side == "LONG"
        assert positions[0].size == 100
        assert positions[0].entry_price == 0.65
        assert positions[0].unrealized_pnl == 5.0
        assert positions[1].side == "SHORT"
        assert positions[1].size == 50

    async def test_get_positions_empty(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(return_value={"clob": []})
        adapter._client = mock_http

        positions = await adapter.get_positions()
        assert positions == []

    async def test_get_balance(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={"balance": 5000.0},
        )
        adapter._client = mock_http

        balance = await adapter.get_balance()
        assert balance == 5000.0

    async def test_get_balance_no_direct_field(self, adapter: LimitlessAdapter):
        """Fallback to alternative field names."""
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={"usdcBalance": "2500.50"},
        )
        adapter._client = mock_http

        balance = await adapter.get_balance()
        assert balance == 2500.50


class TestLimitlessAdapterHelpers:
    def test_extract_outcomes_explicit(self):
        data = {"outcomes": ["YES", "NO"]}
        assert LimitlessAdapter._extract_outcomes(data) == ["YES", "NO"]

    def test_extract_outcomes_from_tokens(self):
        data = {"tokens": {"yes": "0x1", "no": "0x2"}}
        assert LimitlessAdapter._extract_outcomes(data) == ["YES", "NO"]

    def test_extract_outcomes_empty(self):
        assert LimitlessAdapter._extract_outcomes({}) == []

    @pytest.mark.asyncio
    async def test_resolve_token_id_yes(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={"tokens": {"yes": "0xyes123", "no": "0xno456"}},
        )
        adapter._client = mock_http

        token_id = await adapter._resolve_token_id("btc-2024", "BUY")
        assert token_id == "0xyes123"

    @pytest.mark.asyncio
    async def test_resolve_token_id_no(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200)
        mock_http.get.return_value.json = MagicMock(
            return_value={"tokens": {"yes": "0xyes123", "no": "0xno456"}},
        )
        adapter._client = mock_http

        token_id = await adapter._resolve_token_id("btc-2024", "SELL")
        assert token_id == "0xno456"

    @pytest.mark.asyncio
    async def test_resolve_token_id_not_found(self, adapter: LimitlessAdapter):
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.get = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=404)
        adapter._client = mock_http

        token_id = await adapter._resolve_token_id("bad", "BUY")
        assert token_id == ""

    def test_try_init_order_client_no_sdk(self, adapter: LimitlessAdapter):
        """Without limitless_sdk installed, returns None."""
        adapter._config.private_key = "0x" + "ab" * 32
        result = adapter._try_init_order_client()
        assert result is None

    def test_try_init_order_client_no_private_key(self, adapter: LimitlessAdapter):
        """Without private_key, returns None."""
        adapter._config.private_key = ""
        result = adapter._try_init_order_client()
        assert result is None

    def test_get_sdk_enums_no_sdk(self, adapter: LimitlessAdapter):
        """Without limitless_sdk, raises RuntimeError."""
        with pytest.raises(RuntimeError, match="limitless-sdk"):
            adapter._get_sdk_enums()
