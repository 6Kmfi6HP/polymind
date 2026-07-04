"""
Tests for Kalshi exchange adapter — mock-based HTTP integration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from polymind.kalshi.adapter import KalshiAdapter, KalshiConfig


@pytest.fixture
def adapter() -> KalshiAdapter:
    cfg = KalshiConfig(email="test@example.com", password="test123")
    return KalshiAdapter(config=cfg)


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.delete = AsyncMock()
    client.aclose = AsyncMock()
    return client


class TestKalshiAdapter:
    async def test_connect_creates_client(self, adapter: KalshiAdapter):
        """connect() should initialize the HTTP client."""
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock()
        mock_http.post.return_value = MagicMock(status_code=200)
        mock_http.post.return_value.json = MagicMock(return_value={})

        with patch("httpx.AsyncClient", return_value=mock_http):
            await adapter.connect()
            assert adapter._client is not None

    async def test_connect_logs_in(self, adapter: KalshiAdapter):
        """With credentials, connect() should call /login."""
        mock_http = MagicMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock()
        mock_http.post.return_value = MagicMock(status_code=200)
        mock_http.post.return_value.json = MagicMock(return_value={"token": "abc"})

        with patch("httpx.AsyncClient", return_value=mock_http):
            await adapter.connect()
            assert adapter._token == "abc"

    async def test_close(self, adapter: KalshiAdapter):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.aclose = AsyncMock()
        adapter._client = mock_client
        adapter._token = "abc"
        await adapter.close()
        assert adapter._client is None

    async def test_get_markets(self, adapter: KalshiAdapter):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()
        mock_client.get.return_value = MagicMock(status_code=200)
        mock_client.get.return_value.json = MagicMock(
            return_value={
                "markets": [
                    {"id": "mkt1", "title": "Will X happen?", "status": "open"},
                ],
            },
        )
        adapter._client = mock_client

        markets = await adapter.get_markets(active=True)
        assert len(markets) == 1
        assert markets[0].market_id == "mkt1"
        assert markets[0].title == "Will X happen?"

    async def test_get_market_not_found(self, adapter: KalshiAdapter):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()
        mock_client.get.return_value = MagicMock(status_code=404)
        adapter._client = mock_client

        market = await adapter.get_market("nonexistent")
        assert market is None

    async def test_get_order_book(self, adapter: KalshiAdapter):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()
        mock_client.get.return_value = MagicMock(status_code=200)
        mock_client.get.return_value.json = MagicMock(
            return_value={
                "market": {
                    "yes_bids": [{"price": 50, "count": 100}],
                    "yes_asks": [{"price": 55, "count": 200}],
                },
            },
        )
        adapter._client = mock_client

        ob = await adapter.get_order_book("mkt1")
        assert ob is not None
        assert len(ob.bids) == 1
        assert ob.bids[0].price == 50.0
        assert ob.asks[0].size == 200.0

    async def test_get_order_book_not_found(self, adapter: KalshiAdapter):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()
        mock_client.get.return_value = MagicMock(status_code=404)
        adapter._client = mock_client

        ob = await adapter.get_order_book("nonexistent")
        assert ob is None

    async def test_place_order(self, adapter: KalshiAdapter):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock()
        mock_client.post.return_value = MagicMock(status_code=200)
        mock_client.post.return_value.json = MagicMock(
            return_value={
                "order": {"id": "ord1", "status": "open", "filled_count": 0},
            },
        )
        adapter._client = mock_client

        result = await adapter.place_order("mkt1", "yes", 0.50, 100, outcome="YES")
        assert result.order_id == "ord1"
        assert result.status == "open"

    async def test_cancel_order(self, adapter: KalshiAdapter):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.delete = AsyncMock()
        mock_client.delete.return_value = MagicMock(status_code=200)
        adapter._client = mock_client

        assert await adapter.cancel_order("ord1") is True

    async def test_get_positions(self, adapter: KalshiAdapter):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()
        mock_client.get.return_value = MagicMock(status_code=200)
        mock_client.get.return_value.json = MagicMock(
            return_value={
                "positions": [
                    {"market_id": "mkt1", "side": "yes", "count": 50, "price": 45},
                ],
            },
        )
        adapter._client = mock_client

        positions = await adapter.get_positions()
        assert len(positions) == 1
        assert positions[0].market_id == "mkt1"
        assert positions[0].side == "YES"

    async def test_get_balance(self, adapter: KalshiAdapter):
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock()
        mock_client.get.return_value = MagicMock(status_code=200)
        mock_client.get.return_value.json = MagicMock(return_value={"balance": 5000.0})
        adapter._client = mock_client

        balance = await adapter.get_balance()
        assert balance == 5000.0

    async def test_get_markets_without_connect_raises(self, adapter: KalshiAdapter):
        with pytest.raises(RuntimeError, match="Not connected"):
            await adapter.get_markets()
