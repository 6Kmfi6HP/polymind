"""
Abstract exchange adapter interface -- all venue adapters implement this.

PolymarketAdapter (in polymind/polymarket/client.py) will be refactored
to implement this interface in a future phase. New adapters (Kalshi,
Limitless, etc.) implement it from scratch.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MarketInfo:
    """Basic market info returned by any venue."""

    market_id: str
    title: str
    outcomes: list[str] = field(default_factory=list)
    status: str = "active"  # active, closed, settled


@dataclass
class OrderBookLevel:
    """A single bid or ask level."""

    price: float
    size: float


@dataclass
class OrderBook:
    """Order book snapshot."""

    market_id: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    timestamp: datetime


@dataclass
class OrderResult:
    """Result of an order operation."""

    order_id: str
    status: str  # open, filled, cancelled, failed
    market_id: str
    side: str
    price: float
    size: float
    filled_size: float = 0.0
    error: str | None = None


@dataclass
class Position:
    """Open position."""

    market_id: str
    side: str  # long, short
    size: float
    entry_price: float
    unrealized_pnl: float = 0.0


class ExchangeAdapter(ABC):
    """Abstract interface that all venue adapters must implement.

    Each venue (Polymarket, Kalshi, Limitless, etc.) provides a concrete
    subclass wrapping its SDK or REST API.  Strategies and executors written
    against this interface can run on any supported venue.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the venue."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close connection and release resources."""
        ...

    # -- Market data ---------------------------------------------------

    @abstractmethod
    async def get_markets(self, active: bool = True, limit: int = 50) -> list[MarketInfo]:
        """Fetch available markets."""
        ...

    @abstractmethod
    async def get_order_book(self, market_id: str) -> OrderBook | None:
        """Fetch current order book for *market_id*."""
        ...

    # -- Trading -------------------------------------------------------

    @abstractmethod
    async def place_order(
        self, market_id: str, side: str, price: float, size: float, **kwargs: Any
    ) -> OrderResult:
        """Place an order on the venue."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a single open order."""
        ...

    @abstractmethod
    async def cancel_all_orders(self, market_id: str | None = None) -> int:
        """Cancel all open orders, optionally filtered by market."""
        ...

    # -- Account -------------------------------------------------------

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Fetch current open positions."""
        ...

    @abstractmethod
    async def get_balance(self) -> float:
        """Fetch available balance."""
        ...

    # -- Status --------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Venue name, e.g. 'polymarket', 'kalshi'."""
        ...

    @property
    @abstractmethod
    def connected(self) -> bool:
        """True if connected to the venue."""
        ...
