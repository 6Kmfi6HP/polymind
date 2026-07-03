"""
JSONL price-snapshot store — append-only, market-partitioned.

Inspired by the polymarket-cross-sectional-momentum CLOB snapshot store.
Every snapshot is one JSON line; each market_id gets its own file.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional


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
    """Append-only JSONL-backed price snapshot store.

    Uses one JSONL file per market under *path*.
    When ``path`` is ``None``, operates in-memory (useful for testing).
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = Path(path) if path else None
        self._in_memory: list[PriceSnapshot] = []
        self._closed = False

    async def append_snapshot(self, snapshot: PriceSnapshot) -> None:
        """Persist a single PriceSnapshot."""
        self._check_open()
        if self._path is None:
            self._in_memory.append(snapshot)
        else:
            file_path = self._file_for_market(snapshot.market_id)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "a") as f:
                f.write(_snapshot_to_json(snapshot) + "\n")

    async def read_snapshots(
        self,
        market_id: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> AsyncGenerator[PriceSnapshot, None]:
        """Yield PriceSnapshots for *market_id*, optionally filtered by date."""
        self._check_open()
        snapshots = await self.read_snapshots_batch(market_id)
        for s in snapshots:
            if start and s.timestamp < datetime.fromisoformat(start):
                continue
            if end and s.timestamp > datetime.fromisoformat(end):
                continue
            yield s

    async def read_snapshots_batch(
        self, market_id: str, limit: int = 0
    ) -> list[PriceSnapshot]:
        """Read all snapshots for *market_id* as a list (up to *limit*)."""
        self._check_open()
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
        if self._path is None:
            return sum(1 for s in self._in_memory if s.market_id == market_id)
        file_path = self._file_for_market(market_id)
        if not file_path.exists():
            return 0
        with open(file_path) as f:
            return sum(1 for _ in f)

    async def close(self) -> None:
        """Close the store. Further operations raise RuntimeError."""
        self._closed = True

    def _check_open(self) -> None:
        if self._closed:
            raise RuntimeError("PriceStore is closed")

    def _file_for_market(self, market_id: str) -> Path:
        assert self._path is not None
        return self._path / f"{market_id}.jsonl"


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
