"""
Tests for PriceStore (JSONL snapshot store).
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from polymind.storage.price_store import PriceStore, PriceStoreConfig, SnapshotRecord


@pytest.fixture
def temp_dir() -> str:
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path)


@pytest.fixture
def store(temp_dir: str) -> PriceStore:
    cfg = PriceStoreConfig(base_dir=temp_dir, flush_interval=100)
    return PriceStore(cfg)


class TestSnapshotRecord:
    def test_construction(self):
        now = datetime.now()
        rec = SnapshotRecord(
            timestamp=now,
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
        )
        assert rec.market_id == "0xabc"
        assert rec.mid_price == 0.825
        assert rec.bid_size == 100.0


class TestPriceStore:
    def test_append_and_flush(self, store: PriceStore):
        now = datetime.now()
        rec = SnapshotRecord(
            timestamp=now,
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
        )
        store.append(rec)
        store.flush()
        records = store.read_all("0xabc")
        assert len(records) == 1
        assert records[0].market_id == "0xabc"

    def test_multiple_markets(self, store: PriceStore):
        now = datetime.now()
        for mid in ["0xabc", "0xdef"]:
            store.append(
                SnapshotRecord(
                    timestamp=now,
                    market_id=mid,
                    bid_price=0.5,
                    bid_size=100.0,
                    ask_price=0.55,
                    ask_size=200.0,
                    mid_price=0.525,
                )
            )
        store.flush()
        mids = store.get_market_ids()
        assert "0xabc" in mids
        assert "0xdef" in mids

    def test_read_empty(self, store: PriceStore):
        records = store.read_all("nonexistent")
        assert records == []

    def test_auto_flush(self, temp_dir: str):
        """Should flush automatically after flush_interval writes."""
        cfg = PriceStoreConfig(base_dir=temp_dir, flush_interval=5)
        store = PriceStore(cfg)
        now = datetime.now()
        for i in range(5):
            store.append(
                SnapshotRecord(
                    timestamp=now,
                    market_id="0xabc",
                    bid_price=0.5,
                    bid_size=100.0,
                    ask_price=0.55,
                    ask_size=200.0,
                    mid_price=0.525,
                )
            )
        # 5th write should trigger auto-flush
        file_path = Path(temp_dir) / "0xabc.jsonl"
        assert file_path.exists()
        records = store.read_all("0xabc")
        assert len(records) == 5
        store.clear_buffer()
        store.close()

    def test_close_and_clear(self, store: PriceStore):
        now = datetime.now()
        store.append(
            SnapshotRecord(
                timestamp=now,
                market_id="0xabc",
                bid_price=0.5,
                bid_size=100.0,
                ask_price=0.55,
                ask_size=200.0,
                mid_price=0.525,
            )
        )
        store.close()
        assert store._buffers == {}
