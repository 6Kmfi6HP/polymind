"""
Price-snapshot store — JSONL files or DuckDB-backed.

Supports two backends:
- ``jsonl`` (default): one JSONL file per market — simple, portable.
- ``duckdb``: DuckDB table — SQL-queryable, faster for large datasets.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal


@dataclass
class PriceSnapshot:
    """A single CLOB price observation for one market."""

    market_id: str
    timestamp: datetime
    bid_price: float
    ask_price: float
    mid_price: float
    bid_size: float = 0.0
    ask_size: float = 0.0
    volume: float = 0.0
    source: str = "clob"


class PriceStore:
    """Append-only price snapshot store.

    Supports two backends selected via the ``backend`` parameter:

    - ``"jsonl"`` (default): one JSONL file per market under *path*.
      When ``path`` is ``None``, operates in-memory (useful for testing).
    - ``"duckdb"``: stores snapshots in a DuckDB table at *path*.
      When ``path`` is ``None``, uses an in-memory DuckDB database.

    All public methods work identically regardless of backend.
    """

    def __init__(
        self,
        path: str | None = None,
        backend: Literal["jsonl", "duckdb"] = "jsonl",
    ) -> None:
        self._path = Path(path) if path else None
        self._in_memory: list[PriceSnapshot] = []
        self._closed = False
        self._backend = backend
        self._conn: Any = None

    async def _ensure_duckdb(self) -> Any:
        """Lazy-init DuckDB connection."""
        if self._conn is not None:
            return self._conn
        import duckdb

        if self._path is not None:
            db_path = self._path / "prices.duckdb"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = duckdb.connect(str(db_path))
        else:
            self._conn = duckdb.connect(":memory:")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS snapshots ("
            "  market_id VARCHAR,"
            "  timestamp TIMESTAMP,"
            "  bid_price DOUBLE,"
            "  ask_price DOUBLE,"
            "  mid_price DOUBLE,"
            "  bid_size DOUBLE,"
            "  ask_size DOUBLE,"
            "  volume DOUBLE,"
            "  source VARCHAR"
            ")"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_market_ts "
            "ON snapshots (market_id, timestamp)"
        )
        return self._conn

    # ── Public API ─────────────────────────────────────────────────────────

    async def append_snapshot(self, snapshot: PriceSnapshot) -> None:
        """Persist a single PriceSnapshot."""
        self._check_open()
        if self._backend == "duckdb":
            conn = await self._ensure_duckdb()
            conn.execute(
                "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    snapshot.market_id,
                    snapshot.timestamp.replace(tzinfo=None)
                    if snapshot.timestamp.tzinfo
                    else snapshot.timestamp,
                    snapshot.bid_price,
                    snapshot.ask_price,
                    snapshot.mid_price,
                    snapshot.bid_size,
                    snapshot.ask_size,
                    snapshot.volume,
                    snapshot.source,
                ],
            )
        elif self._path is None:
            self._in_memory.append(snapshot)
        else:
            file_path = self._file_for_market(snapshot.market_id)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "a") as f:
                f.write(_snapshot_to_json(snapshot) + "\n")

    async def read_snapshots(
        self,
        market_id: str,
        start: str | None = None,
        end: str | None = None,
    ) -> AsyncGenerator[PriceSnapshot, None]:
        """Yield PriceSnapshots for *market_id*, optionally filtered by date."""
        self._check_open()
        if self._backend == "duckdb":
            conn = await self._ensure_duckdb()
            sql = "SELECT * FROM snapshots WHERE market_id = ?"
            params: list[Any] = [market_id]
            if start:
                sql += " AND timestamp >= ?"
                params.append(datetime.fromisoformat(start))
            if end:
                sql += " AND timestamp <= ?"
                params.append(datetime.fromisoformat(end))
            sql += " ORDER BY timestamp ASC"
            results = conn.execute(sql, params).fetchall()
            columns = [
                "market_id",
                "timestamp",
                "bid_price",
                "ask_price",
                "mid_price",
                "bid_size",
                "ask_size",
                "volume",
                "source",
            ]
            for row in results:
                yield _row_to_snapshot(row, columns)
        else:
            snapshots = await self.read_snapshots_batch(market_id)
            for s in snapshots:
                if start and s.timestamp < datetime.fromisoformat(start):
                    continue
                if end and s.timestamp > datetime.fromisoformat(end):
                    continue
                yield s

    async def read_snapshots_batch(self, market_id: str, limit: int = 0) -> list[PriceSnapshot]:
        """Read all snapshots for *market_id* as a list (up to *limit*)."""
        self._check_open()
        if self._backend == "duckdb":
            conn = await self._ensure_duckdb()
            sql = "SELECT * FROM snapshots WHERE market_id = ? ORDER BY timestamp ASC"
            if limit > 0:
                sql += f" LIMIT {limit}"
            results = conn.execute(sql, [market_id]).fetchall()
            columns = [
                "market_id",
                "timestamp",
                "bid_price",
                "ask_price",
                "mid_price",
                "bid_size",
                "ask_size",
                "volume",
                "source",
            ]
            return [_row_to_snapshot(row, columns) for row in results]
        if self._path is None:
            all_snaps = [s for s in self._in_memory if s.market_id == market_id]
        else:
            file_path = self._file_for_market(market_id)
            if not file_path.exists():
                return []
            all_snaps = []
            with open(file_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_snaps.append(_snapshot_from_json(line))
        if limit > 0:
            return all_snaps[:limit]
        return all_snaps

    async def get_market_ids(self) -> list[str]:
        """Return a sorted list of all market IDs in the store."""
        self._check_open()
        if self._backend == "duckdb":
            conn = await self._ensure_duckdb()
            rows = conn.execute(
                "SELECT DISTINCT market_id FROM snapshots ORDER BY market_id"
            ).fetchall()
            return [r[0] for r in rows]
        if self._path is None:
            ids = {s.market_id for s in self._in_memory}
        else:
            ids = set()
            for f in self._path.glob("*.jsonl"):
                ids.add(f.stem)
        return sorted(ids)

    async def count_snapshots(self, market_id: str) -> int:
        """Return the number of snapshots for *market_id*."""
        self._check_open()
        if self._backend == "duckdb":
            conn = await self._ensure_duckdb()
            row = conn.execute(
                "SELECT COUNT(*) FROM snapshots WHERE market_id = ?", [market_id]
            ).fetchone()
            return row[0] if row else 0
        if self._path is None:
            return sum(1 for s in self._in_memory if s.market_id == market_id)
        file_path = self._file_for_market(market_id)
        if not file_path.exists():
            return 0
        with open(file_path) as f:
            return sum(1 for _ in f)

    async def close(self) -> None:
        """Close the store. Further operations raise RuntimeError."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._closed = True

    def _check_open(self) -> None:
        if self._closed:
            raise RuntimeError("PriceStore is closed")

    def _file_for_market(self, market_id: str) -> Path:
        assert self._path is not None
        return self._path / f"{market_id}.jsonl"


def _row_to_snapshot(row: tuple, columns: list[str]) -> PriceSnapshot:
    """Convert a DuckDB result row to a PriceSnapshot."""
    d = dict(zip(columns, row, strict=False))
    ts = d["timestamp"]
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    return PriceSnapshot(
        market_id=str(d["market_id"]),
        timestamp=ts,
        bid_price=float(d["bid_price"]),
        ask_price=float(d["ask_price"]),
        mid_price=float(d["mid_price"]),
        bid_size=float(d["bid_size"]),
        ask_size=float(d["ask_size"]),
        volume=float(d["volume"]),
        source=str(d.get("source", "clob")),
    )


def _snapshot_to_json(snapshot: PriceSnapshot) -> str:
    d = asdict(snapshot)
    if isinstance(d["timestamp"], datetime):
        d["timestamp"] = d["timestamp"].isoformat()
    return json.dumps(d, sort_keys=True)


def _snapshot_from_json(line: str) -> PriceSnapshot:
    d = json.loads(line)
    if isinstance(d.get("timestamp"), str):
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
    return PriceSnapshot(**d)
