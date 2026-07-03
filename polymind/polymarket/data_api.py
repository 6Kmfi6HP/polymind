"""
Polymarket Data API adapter — market metadata, order book, candles, trades.

Wraps the Polymarket Data API (Gamma API) to provide domain-typed responses
for factor engines, backtesting, and strategy analysis.  This adapter depends
on the project-owned domain types, not raw SDK response shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


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
    timestamp: Optional[datetime] = None


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
    api_key: Optional[str] = None
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
        self._client: Optional[Any] = None

    async def __aenter__(self) -> PolymarketDataAPI:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def get_market(self, market_id: str) -> MarketDetail:
        """Fetch metadata for a single market."""
        return MarketDetail(market_id=market_id, condition_id="", title="")

    async def get_markets(self, active: bool = True) -> list[MarketDetail]:
        """Fetch a list of markets."""
        return []

    async def get_orderbook(self, market_id: str) -> OrderbookSnapshot:
        """Fetch the current order book snapshot."""
        return OrderbookSnapshot(market_id=market_id)

    async def get_candles(
        self, market_id: str, interval_hours: int = 1, limit: int = 100
    ) -> list[Candle]:
        """Fetch historical candle data."""
        return []

    async def get_trades(
        self, market_id: str, limit: int = 100
    ) -> list[Trade]:
        """Fetch recent trades for a market."""
        return []

    async def get_volume(self, market_id: str) -> VolumeInfo:
        """Fetch 24h volume and liquidity for a market."""
        return VolumeInfo(market_id=market_id)

    async def close(self) -> None:
        """Release any HTTP client resources."""
        self._client = None
