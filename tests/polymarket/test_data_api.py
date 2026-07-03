"""Tests for the Polymarket Data API adapter."""

from __future__ import annotations

from datetime import datetime

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


class TestDataAPIConfig:
    def test_defaults(self) -> None:
        cfg = DataAPIConfig()
        assert cfg.base_url == "https://gamma-api.polymarket.com"
        assert cfg.api_key is None
        assert cfg.timeout == 30.0
        assert cfg.rate_limit_per_sec == 10


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


class TestCandle:
    def test_construction(self) -> None:
        ts = datetime(2026, 1, 1, 12, 0)
        c = Candle(timestamp=ts, open=0.5, high=0.55, low=0.48, close=0.52, volume=5000)
        assert c.open == 0.5
        assert c.high == 0.55
        assert c.close == 0.52
        assert c.volume == 5000


class TestTrade:
    def test_construction(self) -> None:
        ts = datetime(2026, 1, 1)
        t = Trade(trade_id="t1", market_id="0xabc", side="BUY", price=0.5, size=100, timestamp=ts)
        assert t.trade_id == "t1"
        assert t.side == "BUY"


class TestVolumeInfo:
    def test_construction(self) -> None:
        vi = VolumeInfo(market_id="0xabc", volume_24h=500_000, liquidity=1_000_000)
        assert vi.volume_24h == 500_000
        assert vi.liquidity == 1_000_000

    def test_defaults(self) -> None:
        vi = VolumeInfo(market_id="0x1")
        assert vi.volume_24h == 0.0


class TestPolymarketDataAPI:
    @pytest.mark.asyncio
    async def test_get_market_returns_default(self) -> None:
        api = PolymarketDataAPI(DataAPIConfig())
        md = await api.get_market("0xabc")
        assert md.market_id == "0xabc"
        await api.close()

    @pytest.mark.asyncio
    async def test_get_markets_returns_empty(self) -> None:
        api = PolymarketDataAPI(DataAPIConfig())
        markets = await api.get_markets()
        assert markets == []
        await api.close()

    @pytest.mark.asyncio
    async def test_get_orderbook_returns_default(self) -> None:
        api = PolymarketDataAPI(DataAPIConfig())
        ob = await api.get_orderbook("0xabc")
        assert ob.market_id == "0xabc"
        assert ob.bids == []
        await api.close()

    @pytest.mark.asyncio
    async def test_get_candles_returns_empty(self) -> None:
        api = PolymarketDataAPI(DataAPIConfig())
        candles = await api.get_candles("0xabc")
        assert candles == []
        await api.close()

    @pytest.mark.asyncio
    async def test_get_trades_returns_empty(self) -> None:
        api = PolymarketDataAPI(DataAPIConfig())
        trades = await api.get_trades("0xabc")
        assert trades == []
        await api.close()

    @pytest.mark.asyncio
    async def test_get_volume_returns_default(self) -> None:
        api = PolymarketDataAPI(DataAPIConfig())
        vi = await api.get_volume("0xabc")
        assert vi.market_id == "0xabc"
        await api.close()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        async with PolymarketDataAPI(DataAPIConfig()) as api:
            md = await api.get_market("0x1")
            assert md.market_id == "0x1"
        assert api._client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self) -> None:
        api = PolymarketDataAPI(DataAPIConfig())
        await api.close()
        await api.close()
