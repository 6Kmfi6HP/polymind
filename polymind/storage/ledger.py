"""Persistent ledger store backed by SQLite.

Wraps DatabaseConnection for append-only ledger entry storage and
position tracking. Uses an in-memory SQLite database when
config.path == ":memory:".
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from polymind.core.ledger import EntryType, LedgerEntry
from polymind.execution.executor import PositionRecord
from polymind.storage.database import DatabaseConfig, DatabaseConnection


class LedgerStore:
    """Wraps a SQLite database for ledger and position persistence.

    Opens a single DatabaseConnection lazily on the first operation
    and keeps it alive until ``close()`` is called.
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._conn: Optional[DatabaseConnection] = None

    # ── public API ─────────────────────────────────────────────────────────

    async def append(self, entry: LedgerEntry) -> None:
        """Persist a ledger entry."""
        conn = await self._ensure_connection()
        await conn.execute(
            """
            INSERT INTO ledger_entries (
                entry_id, entry_type, timestamp, market_id, description,
                delta_cash, delta_position, position_after, cash_after,
                fill_ref, supersedes, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.entry_id,
                entry.entry_type.name,
                entry.timestamp.isoformat(),
                entry.market_id,
                entry.description,
                entry.delta_cash,
                entry.delta_position,
                entry.position_after,
                entry.cash_after,
                entry.fill_ref,
                entry.supersedes,
                json.dumps(entry.metadata),
            ),
        )
        await conn.commit()

    async def get_entries(
        self, market_id: str, limit: int = 100
    ) -> list[LedgerEntry]:
        """Return ledger entries for a market in insertion order."""
        conn = await self._ensure_connection()
        rows = await conn.fetch_all(
            """
            SELECT * FROM ledger_entries
            WHERE market_id = ?
            ORDER BY rowid ASC
            LIMIT ?
            """,
            (market_id, limit),
        )
        return [self._row_to_entry(r) for r in rows]

    async def get_pnl(self, market_id: str) -> float:
        """Return the net P&L for a market (sum of delta_cash)."""
        conn = await self._ensure_connection()
        row = await conn.fetch_one(
            "SELECT COALESCE(SUM(delta_cash), 0.0) AS pnl "
            "FROM ledger_entries WHERE market_id = ?",
            (market_id,),
        )
        return row["pnl"] if row else 0.0

    async def get_cash_balance(self) -> float:
        """Return the latest cash balance from the ledger."""
        conn = await self._ensure_connection()
        row = await conn.fetch_one(
            "SELECT cash_after FROM ledger_entries ORDER BY rowid DESC LIMIT 1"
        )
        return row["cash_after"] if row else 0.0

    async def get_position(
        self, market_id: str
    ) -> Optional[PositionRecord]:
        """Return the stored position for a market, or None."""
        conn = await self._ensure_connection()
        row = await conn.fetch_one(
            "SELECT * FROM positions WHERE market_id = ?",
            (market_id,),
        )
        if row is None:
            return None
        return PositionRecord(
            market_id=row["market_id"],
            outcome=row["outcome"],
            size=row["size"],
            avg_entry=row["avg_entry"],
            realized_pnl=row["realized_pnl"],
        )

    async def update_position(
        self, market_id: str, rec: PositionRecord
    ) -> None:
        """Upsert a position record (insert or replace by market_id)."""
        conn = await self._ensure_connection()
        await conn.execute(
            """
            INSERT INTO positions (market_id, outcome, size, avg_entry, realized_pnl)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(market_id) DO UPDATE SET
                outcome = excluded.outcome,
                size = excluded.size,
                avg_entry = excluded.avg_entry,
                realized_pnl = excluded.realized_pnl
            """,
            (rec.market_id, rec.outcome, rec.size, rec.avg_entry, rec.realized_pnl),
        )
        await conn.commit()

    async def close(self) -> None:
        """Close the underlying database connection (idempotent)."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    # ── internals ─────────────────────────────────────────────────────────

    async def _ensure_connection(self) -> DatabaseConnection:
        """Lazy-open the database connection and initialise tables."""
        if self._conn is None:
            self._conn = DatabaseConnection(self._config)
            await self._conn.__aenter__()
            await self._init_tables()
        return self._conn

    async def _init_tables(self) -> None:
        """Create tables if they do not exist."""
        conn = self._conn
        assert conn is not None
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS ledger_entries (
                entry_id        TEXT PRIMARY KEY,
                entry_type      TEXT NOT NULL,
                timestamp       TEXT NOT NULL,
                market_id       TEXT NOT NULL,
                description     TEXT NOT NULL,
                delta_cash      REAL NOT NULL,
                delta_position  REAL NOT NULL,
                position_after  REAL NOT NULL,
                cash_after      REAL NOT NULL,
                fill_ref        TEXT,
                supersedes      TEXT,
                metadata        TEXT DEFAULT '{}'
            )"""
        )
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS positions (
                market_id       TEXT PRIMARY KEY,
                outcome         TEXT NOT NULL,
                size            REAL NOT NULL,
                avg_entry       REAL NOT NULL,
                realized_pnl    REAL NOT NULL
            )"""
        )
        await conn.commit()

    @staticmethod
    def _row_to_entry(row: dict) -> LedgerEntry:
        """Convert a database row dict back to a LedgerEntry."""
        return LedgerEntry(
            entry_id=row["entry_id"],
            entry_type=EntryType[row["entry_type"]],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            market_id=row["market_id"],
            description=row["description"],
            delta_cash=row["delta_cash"],
            delta_position=row["delta_position"],
            position_after=row["position_after"],
            cash_after=row["cash_after"],
            fill_ref=row.get("fill_ref"),
            supersedes=row.get("supersedes"),
            metadata=json.loads(row.get("metadata", "{}")),
        )
