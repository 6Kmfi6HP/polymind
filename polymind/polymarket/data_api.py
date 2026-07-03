"""
Polymarket Data API adapter — market metadata, order book, candles, trades.

Wraps the Polymarket Data API (Gamma API) to provide domain-typed responses
for factor engines, backtesting, and strategy analysis.  This adapter depends
on the project-owned domain types, not raw SDK response shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp


@dataclass
class MarketDetail:
    """Full market metadata from the Polymarket Data API."""

    market_id: str
    condition_id: str
    title: str
    outcomes: list[str] = field(default_factory=list)
    end_date_iso: str = ""
    volume_24h: float = 0.0
    liquidity: float = 0.0
    tick_size: float = 0.01
    min_size: float = 1.0
    status: str = "active"


@dataclass
class OrderLevel:
    """A single bid or ask level in the order book."""

    price: float
    size: float


@dataclass
class OrderbookSnapshot:
    """Point-in-time order book for a market."""

    market_id: str
    bids: list[OrderLevel] = field(default_factory=list)
    asks: list[OrderLevel] = field(default_factory=list)
    timestamp: datetime | None = None


@dataclass
class Candle:
    """OHLCV candlestick."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    """A single executed trade."""

    trade_id: str
    market_id: str
    side: str
    price: float
    size: float
    timestamp: datetime


@dataclass
class VolumeInfo:
    """Market volume and liquidity summary."""

    market_id: str
    volume_24h: float = 0.0
    liquidity: float = 0.0


@dataclass
class DataAPIConfig:
    """Configuration for the Data API adapter."""

    base_url: str = "https://gamma-api.polymarket.com"
    api_key: str | None = None
    timeout: float = 30.0
    rate_limit_per_sec: int = 10


class PolymarketDataAPI:
    """Data API adapter returning domain-typed market data.

    Encapsulates HTTP calls to the Polymarket Gamma API and returns
    ``MarketDetail``, ``OrderbookSnapshot``, ``Candle``, ``Trade``, or
    ``VolumeInfo`` objects.  No strategy logic leaks into this layer.
    """

    def __init__(self, config: DataAPIConfig) -> None:
        self.config = config
        self._client: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> PolymarketDataAPI:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the underlying aiohttp client session."""
        if self._client is None:
            headers: dict[str, str] = {"Accept": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._client = aiohttp.ClientSession(
                base_url=self.config.base_url,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                headers=headers,
            )
        return self._client

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an HTTP request and return the parsed JSON response."""
        session = await self._get_session()
        async with session.request(method, path, **kwargs) as resp:
            resp.raise_for_status()
            return await resp.json()

    @staticmethod
    def _parse_market(data: dict[str, Any]) -> MarketDetail:
        """Transform a raw API market dict into a ``MarketDetail``."""
        return MarketDetail(
            market_id=data.get("id", ""),
            condition_id=data.get("conditionId", ""),
            title=data.get("title", ""),
            outcomes=list(data.get("outcomes", [])),
            end_date_iso=data.get("endDate", ""),
            volume_24h=float(data.get("volume24hr") or 0.0),
            liquidity=float(data.get("liquidity") or 0.0),
            tick_size=float(data.get("tickSize") or 0.01),
            min_size=float(data.get("minSize") or 1.0),
            status="closed" if data.get("closed", False) else "active",
        )

    @staticmethod
    def _parse_timestamp(ts: Any) -> datetime | None:
        if ts is None:
            return None
        if isinstance(ts, int | float):
            return datetime.utcfromtimestamp(ts)
        if isinstance(ts, str):
            ts_stripped = ts.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(ts_stripped)
            except (ValueError, TypeError):
                return None
        return None

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def get_market(self, market_id: str) -> MarketDetail:
        """Fetch metadata for a single market."""
        data = await self._request("GET", f"/markets/{market_id}")
        return self._parse_market(data)

    async def get_markets(self, active: bool = True) -> list[MarketDetail]:
        """Fetch a list of markets."""
        params: dict[str, str] = {"closed": str(not active).lower()}
        data = await self._request("GET", "/markets", params=params)
        return [self._parse_market(item) for item in data]

    async def get_orderbook(self, market_id: str) -> OrderbookSnapshot:
        """Fetch the current order book snapshot."""
        params = {"market": market_id}
        data = await self._request("GET", "/orderbook", params=params)
        bids = [
            OrderLevel(price=float(b["price"]), size=float(b["size"])) for b in data.get("bids", [])
        ]
        asks = [
            OrderLevel(price=float(a["price"]), size=float(a["size"])) for a in data.get("asks", [])
        ]
        timestamp = self._parse_timestamp(data.get("timestamp"))
        return OrderbookSnapshot(
            market_id=market_id,
            bids=bids,
            asks=asks,
            timestamp=timestamp,
        )

    async def get_candles(
        self, market_id: str, interval_hours: int = 1, limit: int = 100
    ) -> list[Candle]:
        """Fetch historical candle data.

        Parameters
        ----------
        market_id:
            Target market identifier.
        interval_hours:
            Candle width in hours (converted to minutes for the API).
        limit:
            Maximum number of candles to return.
        """
        params: dict[str, str] = {
            "market": market_id,
            "interval": str(interval_hours * 60),
            "limit": str(limit),
        }
        data = await self._request("GET", "/candles", params=params)
        candles: list[Candle] = []
        for c in data:
            timestamp = self._parse_timestamp(c.get("t"))
            if timestamp is None:
                timestamp = datetime.now()
            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=float(c.get("o") or 0.0),
                    high=float(c.get("h") or 0.0),
                    low=float(c.get("l") or 0.0),
                    close=float(c.get("c") or 0.0),
                    volume=float(c.get("v") or 0.0),
                )
            )
        return candles

    async def get_trades(self, market_id: str, limit: int = 100) -> list[Trade]:
        """Fetch recent trades for a market."""
        params: dict[str, str] = {"market": market_id, "limit": str(limit)}
        data = await self._request("GET", "/trades", params=params)
        trades: list[Trade] = []
        for t in data:
            timestamp = self._parse_timestamp(t.get("t"))
            if timestamp is None:
                timestamp = datetime.now()
            trades.append(
                Trade(
                    trade_id=t.get("id", ""),
                    market_id=market_id,
                    side=t.get("side", ""),
                    price=float(t.get("price") or 0.0),
                    size=float(t.get("size") or 0.0),
                    timestamp=timestamp,
                )
            )
        return trades

    async def get_volume(self, market_id: str) -> VolumeInfo:
        """Fetch 24h volume and liquidity for a market."""
        data = await self._request("GET", f"/markets/{market_id}")
        return VolumeInfo(
            market_id=market_id,
            volume_24h=float(data.get("volume24hr") or 0.0),
            liquidity=float(data.get("liquidity") or 0.0),
        )

    async def close(self) -> None:
        """Release any HTTP client resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None
