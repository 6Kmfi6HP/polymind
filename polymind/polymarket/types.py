"""
Shared domain types for Polymarket adapters.

These types are shared between ``client``, ``data_api``, and other adapter modules.
They are the canonical definitions — always import from here rather than
from individual adapter modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class OrderBookLevel:
    """A single bid or ask level in the order book."""

    price: float
    size: float
    num_orders: int = 0


@dataclass
class OrderBookSnapshot:
    """Point-in-time order book snapshot for a token."""

    market_id: str
    token_id: str = ""
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)
    timestamp: datetime | None = None
    tick_size: float = 0.01
    min_order_size: str = "1"


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
