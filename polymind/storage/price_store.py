"""
Append-only CLOB snapshot store using JSONL format.

Replicates the pattern from recallnet/polymarket-cross-sectional-momentum
where each market has its own JSONL file of (bid, ask, mid) snapshots.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class SnapshotRecord:
    """A single CLOB snapshot record."""

    timestamp: datetime
    market_id: str
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    mid_price: float


@dataclass
class PriceStoreConfig:
    """Configuration for PriceStore."""

    base_dir: str = "./data/snapshots"
    flush_interval: int = 100  # flush to disk every N writes


class PriceStore:
    """Append-only CLOB snapshot store.

    Each market gets a separate JSONL file. Snapshots are appended
    immediately; periodic flushes ensure durability.
    """

    def __init__(self, config: Optional[PriceStoreConfig] = None):
        self.config = config or PriceStoreConfig()
        self._buffers: Dict[str, List[str]] = {}
        self._write_count: int = 0

    def append(self, record: SnapshotRecord) -> None:
        """Append a snapshot to the market's JSONL buffer."""
        line = json.dumps({
            "timestamp": record.timestamp.isoformat(),
            "market_id": record.market_id,
            "bid_price": record.bid_price,
            "bid_size": record.bid_size,
            "ask_price": record.ask_price,
            "ask_size": record.ask_size,
            "mid_price": record.mid_price,
        })
        if record.market_id not in self._buffers:
            self._buffers[record.market_id] = []
        self._buffers[record.market_id].append(line)
        self._write_count += 1

        if self._write_count >= self.config.flush_interval:
            self.flush()

    def flush(self) -> None:
        """Flush all buffers to disk."""
        base = Path(self.config.base_dir)
        base.mkdir(parents=True, exist_ok=True)

        for market_id, lines in self._buffers.items():
            if not lines:
                continue
            file_path = base / f"{market_id}.jsonl"
            with open(file_path, "a") as f:
                for line in lines:
                    f.write(line + "\n")
            self._buffers[market_id] = []
        self._write_count = 0

    def read_all(self, market_id: str) -> List[SnapshotRecord]:
        """Read all snapshots for a market from disk."""
        file_path = Path(self.config.base_dir) / f"{market_id}.jsonl"
        if not file_path.exists():
            return []

        records: List[SnapshotRecord] = []
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                records.append(
                    SnapshotRecord(
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        market_id=data["market_id"],
                        bid_price=data["bid_price"],
                        bid_size=data["bid_size"],
                        ask_price=data["ask_price"],
                        ask_size=data["ask_size"],
                        mid_price=data["mid_price"],
                    )
                )
        return records

    def get_market_ids(self) -> List[str]:
        """List all markets that have snapshot files."""
        base = Path(self.config.base_dir)
        if not base.exists():
            return []
        return sorted(
            f.stem for f in base.iterdir() if f.suffix == ".jsonl"
        )

    def clear_buffer(self) -> None:
        """Clear in-memory buffers without flushing."""
        self._buffers.clear()
        self._write_count = 0

    def close(self) -> None:
        """Flush and release resources."""
        self.flush()
        self._buffers.clear()
