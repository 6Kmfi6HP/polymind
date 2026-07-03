"""
Persistent storage for executor state (SQLite backend).

Provides an append-only store for FillEvents and LedgerEntries, with
recovery loading for PaperExecutor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import OrderSide
from polymind.core.ledger import EntryType, LedgerEntry


class LedgerStore:
    """SQLite-backed append-only store for fills and ledger entries.

    Provides persistence across restarts for PaperExecutor state.
    Thread-safe via aiosqlite (single-writer queue).

    Usage::

        store = LedgerStore(":memory:")
        await store.open()
        await store.append_fill(fill_event)
        await store.append_ledger(ledger_entry)
        fills = await store.load_fills()
        await store.close()
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn: Optional["aiosqlite.Connection"] = None  # type: ignore[name-defined]

    async def open(self) -> None:
        """Open the database connection and create tables if needed."""
        import aiosqlite

        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fills (
                fill_id TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                size REAL NOT NULL,
                fee REAL NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                order_id TEXT,
                taker INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS ledger_entries (
                entry_id TEXT PRIMARY KEY,
                entry_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                market_id TEXT NOT NULL,
                description TEXT NOT NULL,
                delta_cash REAL NOT NULL,
                delta_position REAL NOT NULL,
                position_after REAL NOT NULL,
                cash_after REAL NOT NULL,
                fill_ref TEXT,
                supersedes TEXT,
                metadata TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_fills_market ON fills(market_id);
            CREATE INDEX IF NOT EXISTS idx_ledger_market ON ledger_entries(market_id);
            """
        )
        await self._conn.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def append_fill(self, fill: FillEvent) -> None:
        """Persist a FillEvent to the store."""
        if self._conn is None:
            raise RuntimeError("Store not opened. Call open() first.")

        import json

        await self._conn.execute(
            """
            INSERT OR IGNORE INTO fills
                (fill_id, market_id, outcome, side, price, size, fee,
                 timestamp, source, order_id, taker, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fill.fill_id,
                fill.market_id,
                fill.outcome,
                fill.side.value,
                fill.price,
                fill.size,
                fill.fee,
                fill.timestamp.isoformat(),
                fill.source.name,
                fill.order_id,
                1 if fill.taker else 0,
                json.dumps(fill.metadata),
            ),
        )
        await self._conn.commit()

    async def append_ledger(self, entry: LedgerEntry) -> None:
        """Persist a LedgerEntry to the store."""
        if self._conn is None:
            raise RuntimeError("Store not opened. Call open() first.")

        import json

        await self._conn.execute(
            """
            INSERT OR IGNORE INTO ledger_entries
                (entry_id, entry_type, timestamp, market_id, description,
                 delta_cash, delta_position, position_after, cash_after,
                 fill_ref, supersedes, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        await self._conn.commit()

    async def load_fills(self) -> List[FillEvent]:
        """Load all fills from the store."""
        if self._conn is None:
            raise RuntimeError("Store not opened. Call open() first.")

        import json

        cursor = await self._conn.execute(
            "SELECT * FROM fills ORDER BY timestamp ASC"
        )
        rows = await cursor.fetchall()
        results: List[FillEvent] = []
        for row in rows:
            results.append(
                FillEvent(
                    fill_id=row["fill_id"],
                    market_id=row["market_id"],
                    outcome=row["outcome"],
                    side=OrderSide(row["side"]),
                    price=row["price"],
                    size=row["size"],
                    fee=row["fee"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    source=FillSource[row["source"]],
                    order_id=row["order_id"],
                    taker=bool(row["taker"]),
                    metadata=json.loads(row["metadata"]),
                )
            )
        return results

    async def load_ledger(self) -> List[LedgerEntry]:
        """Load all ledger entries from the store."""
        if self._conn is None:
            raise RuntimeError("Store not opened. Call open() first.")

        import json

        cursor = await self._conn.execute(
            "SELECT * FROM ledger_entries ORDER BY timestamp ASC"
        )
        rows = await cursor.fetchall()
        results: List[LedgerEntry] = []
        for row in rows:
            results.append(
                LedgerEntry(
                    entry_id=row["entry_id"],
                    entry_type=EntryType[row["entry_type"]],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    market_id=row["market_id"],
                    description=row["description"],
                    delta_cash=row["delta_cash"],
                    delta_position=row["delta_position"],
                    position_after=row["position_after"],
                    cash_after=row["cash_after"],
                    fill_ref=row["fill_ref"],
                    supersedes=row["supersedes"],
                    metadata=json.loads(row["metadata"]),
                )
            )
        return results

    async def get_fill_count(self) -> int:
        """Return the total number of stored fills."""
        if self._conn is None:
            return 0
        cursor = await self._conn.execute("SELECT COUNT(*) as cnt FROM fills")
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_ledger_count(self) -> int:
        """Return the total number of stored ledger entries."""
        if self._conn is None:
            return 0
        cursor = await self._conn.execute(
            "SELECT COUNT(*) as cnt FROM ledger_entries"
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def clear(self) -> None:
        """Clear all data (for testing / reset)."""
        if self._conn is None:
            return
        await self._conn.execute("DELETE FROM fills")
        await self._conn.execute("DELETE FROM ledger_entries")
        await self._conn.commit()
