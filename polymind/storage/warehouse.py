"""
Research data warehouse — DuckDB-style panels for factor analysis.

Provides structured access to market data, orderbook snapshots, and
trading activity for research and backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MarketPanel:
    """Panel data for a single market over time."""

    market_id: str
    timestamps: list[datetime] = field(default_factory=list)
    mid_prices: list[float] = field(default_factory=list)
    bid_prices: list[float] = field(default_factory=list)
    ask_prices: list[float] = field(default_factory=list)
    spreads_bps: list[float] = field(default_factory=list)
    volumes_24h: list[float] = field(default_factory=list)


@dataclass
class MarketMetadata:
    """Static metadata for a market."""

    market_id: str
    question: str = ""
    outcome_a: str = "YES"
    outcome_b: str = "NO"
    resolution: str | None = None
    volume_24h: float = 0.0
    fee_rate: float = 0.003


class DataWarehouse:
    """Research data warehouse for factor analysis.

    Aggregates market panel data for cross-sectional and
    time-series analysis.
    """

    def __init__(self):
        self._panels: dict[str, MarketPanel] = {}
        self._metadata: dict[str, MarketMetadata] = {}

    def register_market(self, meta: MarketMetadata) -> None:
        """Register a market with its metadata."""
        self._metadata[meta.market_id] = meta
        if meta.market_id not in self._panels:
            self._panels[meta.market_id] = MarketPanel(market_id=meta.market_id)

    def append_snapshot(
        self,
        market_id: str,
        timestamp: datetime,
        mid_price: float,
        bid_price: float = 0.0,
        ask_price: float = 0.0,
        volume_24h: float = 0.0,
    ) -> None:
        """Append a snapshot to a market's panel."""
        if market_id not in self._panels:
            self._panels[market_id] = MarketPanel(market_id=market_id)

        panel = self._panels[market_id]
        panel.timestamps.append(timestamp)
        panel.mid_prices.append(mid_price)
        panel.bid_prices.append(bid_price)
        panel.ask_prices.append(ask_price)
        spread_bps = ((ask_price - bid_price) / mid_price * 10000) if mid_price > 0 else 0.0
        panel.spreads_bps.append(spread_bps)
        panel.volumes_24h.append(volume_24h)

    def get_panel(self, market_id: str) -> MarketPanel | None:
        """Get the full panel for a market."""
        return self._panels.get(market_id)

    def get_metadata(self, market_id: str) -> MarketMetadata | None:
        """Get market metadata."""
        return self._metadata.get(market_id)

    def list_markets(self) -> list[str]:
        """List all registered market IDs."""
        return list(self._metadata.keys())

    def latest_prices(self) -> dict[str, float]:
        """Get the latest mid price for each market."""
        prices: dict[str, float] = {}
        for mid, panel in self._panels.items():
            if panel.mid_prices:
                prices[mid] = panel.mid_prices[-1]
        return prices
