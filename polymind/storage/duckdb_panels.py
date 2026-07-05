"""
DuckDB-powered research panels for market data and factor analysis.

Provides SQL-queryable tables as a high-performance replacement for
the in-memory DataWarehouse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import duckdb


@dataclass
class DuckDBConfig:
    """Configuration for the DuckDB panel store.

    Parameters
    ----------
    path:
        File path for persistent storage, or ``:memory:`` for in-memory.
    read_only:
        Open the database in read-only mode.
    """

    path: str = ":memory:"
    read_only: bool = False


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS market_prices (
    market_id    VARCHAR NOT NULL,
    timestamp    TIMESTAMP NOT NULL,
    bid_price    DOUBLE NOT NULL,
    ask_price    DOUBLE NOT NULL,
    mid_price    DOUBLE NOT NULL,
    bid_size     DOUBLE DEFAULT 0.0,
    ask_size     DOUBLE DEFAULT 0.0,
    volume_24h   DOUBLE DEFAULT 0.0,
    source       VARCHAR DEFAULT 'clob'
);

CREATE TABLE IF NOT EXISTS market_metadata (
    market_id    VARCHAR PRIMARY KEY,
    question     VARCHAR DEFAULT '',
    outcome_a    VARCHAR DEFAULT 'YES',
    outcome_b    VARCHAR DEFAULT 'NO',
    resolution   VARCHAR,
    volume_24h   DOUBLE DEFAULT 0.0,
    fee_rate     DOUBLE DEFAULT 0.003
);

CREATE TABLE IF NOT EXISTS factor_scores (
    market_id    VARCHAR NOT NULL,
    timestamp    TIMESTAMP NOT NULL,
    factor_name  VARCHAR NOT NULL,
    score        DOUBLE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prices_market ON market_prices(market_id);
CREATE INDEX IF NOT EXISTS idx_prices_ts ON market_prices(timestamp);
CREATE INDEX IF NOT EXISTS idx_factors_name ON factor_scores(factor_name);
"""


class DuckDBPanelStore:
    """SQL-queryable market data warehouse backed by DuckDB.

    Usage::

        store = DuckDBPanelStore()
        await store.append_price("mkt1", datetime.now(), 0.45, 0.55, 0.50)
        prices = await store.query_prices("mkt1")
        scores = await store.compute_factors()
    """

    def __init__(self, config: DuckDBConfig | None = None) -> None:
        self._config = config or DuckDBConfig()
        self._conn: duckdb.DuckDBPyConnection | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open the DuckDB connection and initialize schema."""
        self._conn = duckdb.connect(
            self._config.path,
            read_only=self._config.read_only,
        )
        self._conn.execute(SCHEMA_SQL)

    async def close(self) -> None:
        """Close the DuckDB connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _require_conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            raise RuntimeError("DuckDBPanelStore not connected. Call connect() first.")
        return self._conn

    # ── Price ingestion ───────────────────────────────────────────────

    async def append_price(
        self,
        market_id: str,
        timestamp: datetime,
        bid_price: float,
        ask_price: float,
        mid_price: float,
        bid_size: float = 0.0,
        ask_size: float = 0.0,
        volume: float = 0.0,
        source: str = "clob",
    ) -> None:
        """Insert a single price observation.

        Strips timezone info for DuckDB TIMESTAMP compatibility.
        """
        conn = self._require_conn()
        ts_naive = timestamp.replace(tzinfo=None) if timestamp.tzinfo else timestamp
        conn.execute(
            "INSERT INTO market_prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                market_id,
                ts_naive,
                bid_price,
                ask_price,
                mid_price,
                bid_size,
                ask_size,
                volume,
                source,
            ],
        )

    async def append_prices_batch(
        self,
        rows: list[dict[str, Any]],
    ) -> None:
        """Insert multiple price observations in one transaction."""
        conn = self._require_conn()
        for row in rows:
            ts = row.get("timestamp", datetime.now(timezone.utc))
            if isinstance(ts, datetime) and ts.tzinfo:
                ts = ts.replace(tzinfo=None)
            conn.execute(
                "INSERT INTO market_prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    row.get("market_id", ""),
                    ts,
                    row.get("bid_price", 0.0),
                    row.get("ask_price", 0.0),
                    row.get("mid_price", 0.0),
                    row.get("bid_size", 0.0),
                    row.get("ask_size", 0.0),
                    row.get("volume", 0.0),
                    row.get("source", "clob"),
                ],
            )

    # ── Queries ───────────────────────────────────────────────────────

    async def query_prices(
        self,
        market_id: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Query price history for a market, optionally filtered by time."""
        conn = self._require_conn()
        sql = "SELECT * FROM market_prices WHERE market_id = ?"
        params: list[Any] = [market_id]

        if start:
            sql += " AND timestamp >= ?"
            params.append(start)
        if end:
            sql += " AND timestamp <= ?"
            params.append(end)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        result = conn.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]

    async def get_market_list(self) -> list[str]:
        """Return sorted list of all market IDs with price data."""
        conn = self._require_conn()
        result = conn.execute(
            "SELECT DISTINCT market_id FROM market_prices ORDER BY market_id",
        )
        return [row[0] for row in result.fetchall()]

    async def count_prices(self, market_id: str) -> int:
        """Count price observations for a market."""
        conn = self._require_conn()
        result = conn.execute(
            "SELECT COUNT(*) FROM market_prices WHERE market_id = ?",
            [market_id],
        )
        row = result.fetchone()
        return row[0] if row is not None else 0

    # ── Metadata ──────────────────────────────────────────────────────

    async def register_market(
        self,
        market_id: str,
        question: str = "",
        outcome_a: str = "YES",
        outcome_b: str = "NO",
        fee_rate: float = 0.003,
    ) -> None:
        """Register or update market metadata."""
        conn = self._require_conn()
        conn.execute(
            "INSERT OR REPLACE INTO market_metadata "
            "(market_id, question, outcome_a, outcome_b, fee_rate) "
            "VALUES (?, ?, ?, ?, ?)",
            [market_id, question, outcome_a, outcome_b, fee_rate],
        )

    async def get_metadata(self, market_id: str) -> dict[str, Any] | None:
        """Return metadata for a market, or None."""
        conn = self._require_conn()
        result = conn.execute(
            "SELECT * FROM market_metadata WHERE market_id = ?",
            [market_id],
        )
        row = result.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in result.description]
        return dict(zip(columns, row, strict=False))

    # ── Factor scores ─────────────────────────────────────────────────

    async def store_factor_score(
        self,
        market_id: str,
        factor_name: str,
        score: float,
        timestamp: datetime | None = None,
    ) -> None:
        """Store a factor score for a market."""
        conn = self._require_conn()
        ts = timestamp or datetime.now(timezone.utc)
        if isinstance(ts, datetime) and ts.tzinfo:
            ts = ts.replace(tzinfo=None)
        conn.execute(
            "INSERT INTO factor_scores VALUES (?, ?, ?, ?)",
            [market_id, ts, factor_name, score],
        )

    async def query_factor_scores(
        self,
        factor_name: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query factor scores, ordered by score descending."""
        conn = self._require_conn()
        result = conn.execute(
            "SELECT market_id, timestamp, score FROM factor_scores "
            "WHERE factor_name = ? ORDER BY score DESC LIMIT ?",
            [factor_name, limit],
        )
        columns = [desc[0] for desc in result.description]
        return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]

    # ── Analytics ─────────────────────────────────────────────────────

    async def get_market_summary(
        self,
        market_id: str,
    ) -> dict[str, Any]:
        """Return summary statistics for a market."""
        conn = self._require_conn()
        result = conn.execute(
            "SELECT "
            "  COUNT(*) AS num_observations,"
            "  AVG(mid_price) AS avg_mid,"
            "  MIN(mid_price) AS min_mid,"
            "  MAX(mid_price) AS max_mid,"
            "  AVG(ask_price - bid_price) AS avg_spread,"
            "  MIN(timestamp) AS first_seen,"
            "  MAX(timestamp) AS last_seen "
            "FROM market_prices WHERE market_id = ?",
            [market_id],
        )
        row = result.fetchone()
        if row is None or row[0] == 0:
            return {}
        columns = [desc[0] for desc in result.description]
        return dict(zip(columns, row, strict=False))
