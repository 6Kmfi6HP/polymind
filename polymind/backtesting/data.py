"""
Data loading and management for backtesting.

Provides abstractions for loading historical market data from various
sources (JSONL, CSV, DuckDB, or in-memory) and converting them into
MarketDataPoint objects for backtesting.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import AsyncGenerator, List, Optional

from polymind.execution.fill_model import MarketSnapshot


class DataSource(Enum):
    """Supported data source formats for backtesting data."""

    JSONL = auto()
    CSV = auto()
    DUCKDB = auto()
    IN_MEMORY = auto()


@dataclass
class BacktestDataConfig:
    """Configuration for loading backtesting data.

    Attributes:
        source: The data source type.
        path: File path or connection string for the data source.
        start_date: Optional inclusive start date filter (ISO format).
        end_date: Optional inclusive end date filter (ISO format).
        market_ids: Optional list of market IDs to filter on.
    """

    source: DataSource
    path: str = ""
    start_date: str | None = None
    end_date: str | None = None
    market_ids: list[str] | None = None


@dataclass
class MarketDataPoint:
    """A single snapshot of market data at a point in time.

    Attributes:
        market_id: The market identifier.
        timestamp: When this snapshot was recorded.
        bid_price: Current best bid price.
        ask_price: Current best ask price.
        mid_price: Midpoint between bid and ask.
        bid_size: Size available at the best bid.
        ask_size: Size available at the best ask.
        volume: Cumulative trading volume.
    """

    market_id: str
    timestamp: datetime
    bid_price: float
    ask_price: float
    mid_price: float
    bid_size: float
    ask_size: float
    volume: float

    def to_market_snapshot(self) -> MarketSnapshot:
        """Convert to a MarketSnapshot for fill simulation."""
        return MarketSnapshot(
            market_id=self.market_id,
            bid_price=self.bid_price,
            bid_size=self.bid_size,
            ask_price=self.ask_price,
            ask_size=self.ask_size,
            mid_price=self.mid_price,
            timestamp=self.timestamp,
        )


class DataLoader:
    """Loads historical market data from various sources.

    Supports JSONL, CSV, DuckDB, and in-memory data sources.
    Data points can be pre-loaded via the constructor or
    ``load_in_memory()`` and filtered at query time by
    :class:`BacktestDataConfig`.
    """

    def __init__(self, data: list[MarketDataPoint] | None = None) -> None:
        self._data: list[MarketDataPoint] = list(data) if data is not None else []

    def load_in_memory(self, data: list[MarketDataPoint]) -> None:
        """Load data points directly into memory (replaces existing)."""
        self._data = list(data)

    async def load_snapshots(
        self, config: BacktestDataConfig
    ) -> AsyncGenerator[MarketDataPoint, None]:
        """Yield MarketDataPoint objects matching *config* filters.

        Args:
            config: Configuration specifying source and filters.

        Yields:
            MarketDataPoint objects matching the query.
        """
        if config.source == DataSource.IN_MEMORY:
            for dp in self._data:
                if self._matches(dp, config):
                    yield dp
        elif config.source == DataSource.JSONL:
            async for dp in self._load_jsonl(config):
                yield dp
        elif config.source == DataSource.CSV:
            async for dp in self._load_csv(config):
                yield dp
        elif config.source == DataSource.DUCKDB:
            async for dp in self._load_duckdb(config):
                yield dp

    async def load_snapshots_batch(
        self, config: BacktestDataConfig
    ) -> list[MarketDataPoint]:
        """Load all matching snapshots into a list."""
        return [dp async for dp in self.load_snapshots(config)]

    async def get_market_ids(
        self, config: BacktestDataConfig
    ) -> list[str]:
        """Return the distinct market IDs available in the data source."""
        ids: set[str] = set()
        async for dp in self.load_snapshots(config):
            ids.add(dp.market_id)
        return sorted(ids)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _matches(self, dp: MarketDataPoint, config: BacktestDataConfig) -> bool:
        """Check whether a data point passes the config filters."""
        if config.market_ids is not None and dp.market_id not in config.market_ids:
            return False
        if config.start_date is not None:
            start = datetime.fromisoformat(config.start_date)
            if dp.timestamp < start:
                return False
        if config.end_date is not None:
            end = datetime.fromisoformat(config.end_date)
            if dp.timestamp > end:
                return False
        return True

    async def _load_jsonl(
        self, config: BacktestDataConfig
    ) -> AsyncGenerator[MarketDataPoint, None]:
        """Load data points from a newline-delimited JSON file."""
        with open(config.path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                dp = _record_to_point(record)
                if self._matches(dp, config):
                    yield dp

    async def _load_csv(
        self, config: BacktestDataConfig
    ) -> AsyncGenerator[MarketDataPoint, None]:
        """Load data points from a CSV file.

        Expected columns: ``market_id``, ``timestamp``, ``bid_price``,
        ``ask_price``, ``mid_price``, ``bid_size``, ``ask_size``, ``volume``.
        """
        with open(config.path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                dp = _record_to_point(row)
                if self._matches(dp, config):
                    yield dp

    async def _load_duckdb(
        self, config: BacktestDataConfig
    ) -> AsyncGenerator[MarketDataPoint, None]:
        """Load data points from a DuckDB database.

        Expects a table named ``market_data`` with columns matching
        the ``MarketDataPoint`` fields.
        """
        import duckdb

        conn = duckdb.connect(config.path)
        try:
            results = conn.execute(
                "SELECT market_id, timestamp, bid_price, ask_price, "
                "mid_price, bid_size, ask_size, volume "
                "FROM market_data"
            ).fetchall()
            for row in results:
                ts = (
                    datetime.fromisoformat(str(row[1]))
                    if isinstance(row[1], str)
                    else row[1]
                )
                dp = MarketDataPoint(
                    market_id=str(row[0]),
                    timestamp=ts,
                    bid_price=float(row[2]),
                    ask_price=float(row[3]),
                    mid_price=float(row[4]),
                    bid_size=float(row[5]),
                    ask_size=float(row[6]),
                    volume=float(row[7]),
                )
                if self._matches(dp, config):
                    yield dp
        finally:
            conn.close()


def _record_to_point(record: dict) -> MarketDataPoint:
    """Convert a dictionary record to a MarketDataPoint."""
    return MarketDataPoint(
        market_id=record["market_id"],
        timestamp=datetime.fromisoformat(record["timestamp"]),
        bid_price=float(record["bid_price"]),
        ask_price=float(record["ask_price"]),
        mid_price=float(record["mid_price"]),
        bid_size=float(record["bid_size"]),
        ask_size=float(record["ask_size"]),
        volume=float(record["volume"]),
    )
