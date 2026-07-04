"""Tests for the Polymarket Data API adapter."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polymind.polymarket.data_api import (
    Candle,
    DataAPIConfig,
    MarketDetail,
    OrderbookSnapshot,
    OrderLevel,
    PolymarketDataAPI,
    Trade,
    VolumeInfo,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestDataAPIConfig:
    def test_defaults(self) -> None:
        cfg = DataAPIConfig()
        assert cfg.base_url == "https://gamma-api.polymarket.com"
        assert cfg.api_key is None
        assert cfg.timeout == 30.0
        assert cfg.rate_limit_per_sec == 10

    def test_custom_values(self) -> None:
        cfg = DataAPIConfig(
            base_url="http://localhost:8000",
            api_key="sk-test",
            timeout=15.0,
            rate_limit_per_sec=5,
        )
        assert cfg.base_url == "http://localhost:8000"
        assert cfg.api_key == "sk-test"
        assert cfg.timeout == 15.0
        assert cfg.rate_limit_per_sec == 5


# ---------------------------------------------------------------------------
# Domain type construction
# ---------------------------------------------------------------------------


class TestMarketDetail:
    def test_construction(self) -> None:
        md = MarketDetail(
            market_id="0xabc",
            condition_id="0xcond",
            title="Will X happen?",
            outcomes=["Yes", "No"],
            end_date_iso="2026-12-31",
            volume_24h=100_000.0,
        )
        assert md.market_id == "0xabc"
        assert md.title == "Will X happen?"
        assert md.volume_24h == 100_000.0
        assert md.status == "active"

    def test_defaults(self) -> None:
        md = MarketDetail(market_id="0x1", condition_id="", title="")
        assert md.tick_size == 0.01
        assert md.min_size == 1.0
        assert md.status == "active"


class TestOrderLevel:
    def test_construction(self) -> None:
        ol = OrderLevel(price=0.55, size=100.0)
        assert ol.price == 0.55
        assert ol.size == 100.0


class TestOrderbookSnapshot:
    def test_construction(self) -> None:
        bids = [OrderLevel(0.5, 50), OrderLevel(0.49, 200)]
        asks = [OrderLevel(0.51, 100)]
        ob = OrderbookSnapshot(market_id="0xabc", bids=bids, asks=asks)
        assert ob.market_id == "0xabc"
        assert len(ob.bids) == 2
        assert len(ob.asks) == 1
        assert ob.bids[0].price == 0.5

    def test_defaults(self) -> None:
        ob = OrderbookSnapshot(market_id="0x1")
        assert ob.bids == []
        assert ob.asks == []

    def test_timestamp_optional(self) -> None:
        ts = datetime(2026, 7, 1, 12, 0)
        ob = OrderbookSnapshot(market_id="0x1", timestamp=ts)
        assert ob.timestamp == ts


class TestCandle:
    def test_construction(self) -> None:
        ts = datetime(2026, 1, 1, 12, 0)
        c = Candle(timestamp=ts, open=0.5, high=0.55, low=0.48, close=0.52, volume=5000.0)
        assert c.open == 0.5
        assert c.high == 0.55
        assert c.close == 0.52
        assert c.volume == 5000.0


class TestTrade:
    def test_construction(self) -> None:
        ts = datetime(2026, 1, 1)
        t = Trade(trade_id="t1", market_id="0xabc", side="BUY", price=0.5, size=100.0, timestamp=ts)
        assert t.trade_id == "t1"
        assert t.side == "BUY"

    def test_defaults_are_strings(self) -> None:
        ts = datetime(2026, 1, 1)
        t = Trade(trade_id="", market_id="0x1", side="", price=0.0, size=0.0, timestamp=ts)
        assert t.trade_id == ""
        assert t.side == ""


class TestVolumeInfo:
    def test_construction(self) -> None:
        vi = VolumeInfo(market_id="0xabc", volume_24h=500_000, liquidity=1_000_000)
        assert vi.volume_24h == 500_000
        assert vi.liquidity == 1_000_000

    def test_defaults(self) -> None:
        vi = VolumeInfo(market_id="0x1")
        assert vi.volume_24h == 0.0
        assert vi.liquidity == 0.0


# ---------------------------------------------------------------------------
# PolymarketDataAPI — real logic with mocked HTTP
# ---------------------------------------------------------------------------


def _api() -> PolymarketDataAPI:
    """Build a test API instance with a minimal config."""
    return PolymarketDataAPI(DataAPIConfig(base_url="http://test.local"))


def _mock_response(body: dict | list) -> MagicMock:
    """Create a fake aiohttp response that works as an async context manager."""
    resp = MagicMock()
    resp.__aenter__.return_value = resp
    resp.__aexit__.return_value = None
    resp.raise_for_status.return_value = None
    resp.json = AsyncMock(return_value=body)
    return resp


def _mock_session() -> MagicMock:
    """Create a fake aiohttp ClientSession with a ``request`` that returns a response."""
    session = MagicMock()
    return session


class TestPolymarketDataAPI:
    """Core adapter tests that mock the internal ``_request`` method."""

    # -- get_market -------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_market(self) -> None:
        api = _api()
        raw_data = {
            "id": "0xabc",
            "conditionId": "0xcond1",
            "title": "Will it rain?",
            "outcomes": ["Yes", "No"],
            "endDate": "2026-12-31T23:59:59Z",
            "volume24hr": "50000.0",
            "liquidity": "200000.0",
            "tickSize": "0.01",
            "minSize": "1.0",
            "closed": False,
        }
        with patch.object(api, "_request", AsyncMock(return_value=raw_data)):
            md = await api.get_market("0xabc")
        assert md.market_id == "0xabc"
        assert md.condition_id == "0xcond1"
        assert md.title == "Will it rain?"
        assert md.outcomes == ["Yes", "No"]
        assert md.volume_24h == 50000.0
        assert md.liquidity == 200000.0
        assert md.status == "active"
        await api.close()

    @pytest.mark.asyncio
    async def test_get_market_closed(self) -> None:
        api = _api()
        raw_data = {"id": "0x1", "closed": True}
        with patch.object(api, "_request", AsyncMock(return_value=raw_data)):
            md = await api.get_market("0x1")
        assert md.status == "closed"
        await api.close()

    @pytest.mark.asyncio
    async def test_get_market_missing_fields(self) -> None:
        api = _api()
        with patch.object(api, "_request", AsyncMock(return_value={})):
            md = await api.get_market("0xempty")
        assert md.market_id == ""
        assert md.condition_id == ""
        assert md.title == ""
        assert md.volume_24h == 0.0
        assert md.liquidity == 0.0
        await api.close()

    # -- get_markets ------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_markets(self) -> None:
        api = _api()
        raw_list = [
            {"id": "0x1", "conditionId": "c1", "title": "Market A", "closed": False},
            {"id": "0x2", "conditionId": "c2", "title": "Market B", "closed": True},
        ]
        with patch.object(api, "_request", AsyncMock(return_value=raw_list)):
            markets = await api.get_markets(active=True)
        assert len(markets) == 2
        assert markets[0].market_id == "0x1"
        assert markets[1].market_id == "0x2"
        assert markets[0].status == "active"
        assert markets[1].status == "closed"
        await api.close()

    @pytest.mark.asyncio
    async def test_get_markets_empty(self) -> None:
        api = _api()
        with patch.object(api, "_request", AsyncMock(return_value=[])):
            markets = await api.get_markets()
        assert markets == []
        await api.close()

    # -- get_orderbook ----------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_orderbook(self) -> None:
        api = _api()
        raw = {
            "market": "0xabc",
            "bids": [{"price": "0.50", "size": "100.0"}, {"price": "0.49", "size": "250.0"}],
            "asks": [{"price": "0.51", "size": "150.0"}],
            "timestamp": 1780000000,
        }
        with patch.object(api, "_request", AsyncMock(return_value=raw)):
            ob = await api.get_orderbook("0xabc")
        assert ob.market_id == "0xabc"
        assert len(ob.bids) == 2
        assert len(ob.asks) == 1
        assert ob.bids[0] == OrderLevel(0.50, 100.0)
        assert ob.bids[1] == OrderLevel(0.49, 250.0)
        assert ob.asks[0] == OrderLevel(0.51, 150.0)
        assert ob.timestamp is not None
        assert isinstance(ob.timestamp, datetime)
        await api.close()

    @pytest.mark.asyncio
    async def test_get_orderbook_empty_levels(self) -> None:
        api = _api()
        raw = {"market": "0x1", "bids": [], "asks": []}
        with patch.object(api, "_request", AsyncMock(return_value=raw)):
            ob = await api.get_orderbook("0x1")
        assert ob.bids == []
        assert ob.asks == []
        assert ob.timestamp is None
        await api.close()

    # -- get_candles ------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_candles(self) -> None:
        api = _api()
        raw = [
            {"t": 1780000000, "o": "0.50", "h": "0.55", "l": "0.48", "c": "0.52", "v": "5000"},
            {"t": 1780003600, "o": "0.52", "h": "0.54", "l": "0.51", "c": "0.53", "v": "3200"},
        ]
        with patch.object(api, "_request", AsyncMock(return_value=raw)):
            candles = await api.get_candles("0xabc", interval_hours=1, limit=2)
        assert len(candles) == 2
        c0 = candles[0]
        assert c0.open == 0.50
        assert c0.high == 0.55
        assert c0.low == 0.48
        assert c0.close == 0.52
        assert c0.volume == 5000.0
        assert isinstance(c0.timestamp, datetime)
        await api.close()

    @pytest.mark.asyncio
    async def test_get_candles_empty(self) -> None:
        api = _api()
        with patch.object(api, "_request", AsyncMock(return_value=[])):
            candles = await api.get_candles("0xabc")
        assert candles == []
        await api.close()

    # -- get_trades -------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_trades(self) -> None:
        api = _api()
        raw = [
            {"id": "t1", "side": "BUY", "price": "0.50", "size": "100.0", "t": 1780000000},
            {"id": "t2", "side": "SELL", "price": "0.51", "size": "50.0", "t": 1780003600},
        ]
        with patch.object(api, "_request", AsyncMock(return_value=raw)):
            trades = await api.get_trades("0xabc", limit=2)
        assert len(trades) == 2
        assert trades[0].trade_id == "t1"
        assert trades[0].side == "BUY"
        assert trades[0].price == 0.50
        assert trades[0].size == 100.0
        assert trades[1].trade_id == "t2"
        assert trades[1].side == "SELL"
        assert trades[1].price == 0.51
        assert trades[1].size == 50.0
        await api.close()

    @pytest.mark.asyncio
    async def test_get_trades_empty(self) -> None:
        api = _api()
        with patch.object(api, "_request", AsyncMock(return_value=[])):
            trades = await api.get_trades("0xabc")
        assert trades == []
        await api.close()

    # -- get_volume -------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_volume(self) -> None:
        api = _api()
        raw = {"id": "0xabc", "volume24hr": "75000.0", "liquidity": "300000.0"}
        with patch.object(api, "_request", AsyncMock(return_value=raw)):
            vi = await api.get_volume("0xabc")
        assert vi.market_id == "0xabc"
        assert vi.volume_24h == 75000.0
        assert vi.liquidity == 300000.0
        await api.close()

    @pytest.mark.asyncio
    async def test_get_volume_zero_defaults(self) -> None:
        api = _api()
        with patch.object(api, "_request", AsyncMock(return_value={})):
            vi = await api.get_volume("0x1")
        assert vi.market_id == "0x1"
        assert vi.volume_24h == 0.0
        assert vi.liquidity == 0.0
        await api.close()

    # -- _request internal plumbing ---------------------------------------

    @pytest.mark.asyncio
    async def test_request_makes_http_call(self) -> None:
        """Verify that _request constructs a GET with the right path and returns JSON."""
        api = _api()
        fake_json = {"id": "42"}
        resp_mock = _mock_response(fake_json)
        session = MagicMock()
        session.request = MagicMock(return_value=resp_mock)

        with patch.object(api, "_get_session", AsyncMock(return_value=session)):
            result = await api._request("GET", "/markets/42")

        assert result == fake_json
        session.request.assert_called_once_with("GET", "/markets/42")
        await api.close()

    @pytest.mark.asyncio
    async def test_request_uses_base_url(self) -> None:
        """Verify that sessions are created with the configured base_url."""
        cfg = DataAPIConfig(base_url="http://custom.local", api_key="test-key")
        api = PolymarketDataAPI(cfg)
        session = await api._get_session()
        assert str(session._base_url) == "http://custom.local"
        # Verify auth header was set
        assert session._default_headers.get("Authorization") == "Bearer test-key"
        await api.close()

    # -- error handling ---------------------------------------------------

    @pytest.mark.asyncio
    async def test_http_error(self) -> None:
        api = _api()
        import aiohttp

        resp = MagicMock()
        resp.__aenter__.return_value = resp
        resp.__aexit__.return_value = None
        resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=404,
            message="Not Found",
            headers={},
        )

        session = MagicMock()
        session.request = MagicMock(return_value=resp)

        with (
            patch.object(api, "_get_session", AsyncMock(return_value=session)),
            pytest.raises(aiohttp.ClientResponseError) as exc_info,
        ):
            await api.get_market("0xmissing")
        assert exc_info.value.status == 404
        await api.close()

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        api = _api()
        import asyncio

        session = MagicMock()
        session.request = MagicMock(side_effect=asyncio.TimeoutError("Request timed out"))

        with (
            patch.object(api, "_get_session", AsyncMock(return_value=session)),
            pytest.raises(asyncio.TimeoutError),
        ):
            await api.get_market("0xslow")
        await api.close()

    @pytest.mark.asyncio
    async def test_auth_failure(self) -> None:
        """Auth failure surfaces as a 403 HTTP error."""
        api = _api()
        import aiohttp

        resp = MagicMock()
        resp.__aenter__.return_value = resp
        resp.__aexit__.return_value = None
        resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=403,
            message="Forbidden",
            headers={},
        )

        session = MagicMock()
        session.request = MagicMock(return_value=resp)

        with (
            patch.object(api, "_get_session", AsyncMock(return_value=session)),
            pytest.raises(aiohttp.ClientResponseError) as exc_info,
        ):
            await api.get_market("0xsecret")
        assert exc_info.value.status == 403
        await api.close()

    # -- context manager & lifecycle --------------------------------------

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        async with PolymarketDataAPI(DataAPIConfig()) as api:
            assert api._client is None
            # Trigger session creation
            _ = await api._get_session()
            assert api._client is not None
        # After exit, client should be closed
        assert api._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self) -> None:
        api = PolymarketDataAPI(DataAPIConfig())
        await api.close()
        await api.close()
        assert api._client is None

    @pytest.mark.asyncio
    async def test_session_reused(self) -> None:
        api = _api()
        s1 = await api._get_session()
        s2 = await api._get_session()
        assert s1 is s2
        await api.close()

    @pytest.mark.asyncio
    async def test_session_created_after_close(self) -> None:
        api = _api()
        s1 = await api._get_session()
        await api.close()
        s2 = await api._get_session()
        assert s2 is not s1
        assert s2.closed is False
        await api.close()

    # -- edge cases: _parse_market, _parse_timestamp ---------------------

    def test_parse_market_none_values(self) -> None:
        raw = {
            "id": "0x1",
            "conditionId": "c1",
            "volume24hr": None,
            "liquidity": None,
            "tickSize": None,
            "minSize": None,
            "closed": False,
        }
        md = PolymarketDataAPI._parse_market(raw)
        assert md.volume_24h == 0.0
        assert md.liquidity == 0.0
        assert md.tick_size == 0.01
        assert md.min_size == 1.0

    def test_parse_timestamp_none(self) -> None:
        assert PolymarketDataAPI._parse_timestamp(None) is None

    def test_parse_timestamp_int(self) -> None:
        ts = PolymarketDataAPI._parse_timestamp(1780000000)
        assert ts is not None
        assert isinstance(ts, datetime)

    def test_parse_timestamp_iso_string(self) -> None:
        ts = PolymarketDataAPI._parse_timestamp("2026-07-01T12:00:00Z")
        assert ts is not None
        assert ts.year == 2026

    def test_parse_timestamp_bad_string(self) -> None:
        assert PolymarketDataAPI._parse_timestamp("not-a-date") is None

    def test_parse_timestamp_unknown_type(self) -> None:
        """Line 111: non-standard type returns None."""
        assert PolymarketDataAPI._parse_timestamp([1, 2, 3]) is None
        assert PolymarketDataAPI._parse_timestamp({"key": "val"}) is None


class TestGetCandlesEdgeCoverage:
    """Cover lines 169-172 (candle timestamp fallback) and 191-193 (trade timestamp fallback)."""

    @pytest.mark.asyncio
    async def test_get_candles_timestamp_fallback(self) -> None:
        """Line 172: candle with missing/invalid timestamp gets datetime.now."""
        api = _api()
        raw = [{"t": None, "o": "0.50", "h": "0.55", "l": "0.48", "c": "0.52", "v": "5000"}]
        with patch.object(api, "_request", AsyncMock(return_value=raw)):
            candles = await api.get_candles("0xabc", interval_hours=1, limit=1)
        assert len(candles) == 1
        assert isinstance(candles[0].timestamp, datetime)
        await api.close()

    @pytest.mark.asyncio
    async def test_get_trades_timestamp_fallback(self) -> None:
        """Line 193: trade with missing/invalid timestamp gets datetime.now."""
        api = _api()
        raw = [{"id": "t1", "side": "BUY", "price": "0.50", "size": "100.0", "t": None}]
        with patch.object(api, "_request", AsyncMock(return_value=raw)):
            trades = await api.get_trades("0xabc", limit=1)
        assert len(trades) == 1
        assert isinstance(trades[0].timestamp, datetime)
        await api.close()
