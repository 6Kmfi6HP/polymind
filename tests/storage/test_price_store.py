"""Tests for the JSONL price-store."""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.storage.price_store import PriceSnapshot, PriceStore


def _snap(
    market_id: str = "0xabc",
    timestamp: str = "2026-01-15T12:00:00",
    bid: float = 0.40,
    ask: float = 0.60,
    bid_size: float = 1000.0,
    ask_size: float = 800.0,
    **kwargs,
) -> PriceSnapshot:
    return PriceSnapshot(
        market_id=market_id,
        timestamp=datetime.fromisoformat(timestamp),
        bid_price=bid,
        ask_price=ask,
        mid_price=(bid + ask) / 2.0,
        bid_size=bid_size,
        ask_size=ask_size,
        **kwargs,
    )


# ── Construction ────────────────────────────────────────────────────────


class TestPriceSnapshot:
    def test_construct_minimal(self) -> None:
        snap = PriceSnapshot(
            market_id="0xabc",
            timestamp=datetime(2026, 1, 15, 12, 0, 0),
            bid_price=0.40,
            ask_price=0.60,
            mid_price=0.50,
        )
        assert snap.market_id == "0xabc"
        assert snap.mid_price == 0.50
        assert snap.source == "clob"  # default

    def test_construct_full(self) -> None:
        snap = PriceSnapshot(
            market_id="0xabc",
            timestamp=datetime(2026, 1, 15, 12, 0, 0),
            bid_price=0.40,
            ask_price=0.60,
            mid_price=0.50,
            bid_size=1000.0,
            ask_size=800.0,
            volume=5000.0,
            source="custom",
        )
        assert snap.volume == 5000.0
        assert snap.source == "custom"

    def test_mid_price_computed_correctly(self) -> None:
        mid = (0.40 + 0.60) / 2.0
        snap = PriceSnapshot(
            market_id="m",
            timestamp=datetime(2026, 1, 15, 12, 0, 0),
            bid_price=0.40,
            ask_price=0.60,
            mid_price=mid,
        )
        assert snap.mid_price == 0.50


# ── In-memory store tests ───────────────────────────────────────────────


class TestPriceStoreMemory:
    @pytest.fixture
    async def store(self) -> PriceStore:
        s = PriceStore(path=None)  # in-memory
        yield s
        await s.close()

    async def test_append_and_read_batch(self, store: PriceStore) -> None:
        s1 = _snap("0xabc", "2026-01-15T12:00:00", bid=0.40, ask=0.60)
        s2 = _snap("0xabc", "2026-01-15T12:01:00", bid=0.41, ask=0.61)
        await store.append_snapshot(s1)
        await store.append_snapshot(s2)

        snaps = await store.read_snapshots_batch("0xabc")
        assert len(snaps) == 2
        assert snaps[0].bid_price == 0.40
        assert snaps[1].bid_price == 0.41

    async def test_read_snapshots_generator_yields_in_order(self, store: PriceStore) -> None:
        ts = [
            "2026-01-15T12:00:00",
            "2026-01-15T12:01:00",
            "2026-01-15T12:02:00",
        ]
        for i, t in enumerate(ts):
            await store.append_snapshot(_snap("0xabc", t, bid=0.40 + i * 0.01, ask=0.60 + i * 0.01))

        prices = []
        async for snap in store.read_snapshots("0xabc"):
            prices.append(snap.bid_price)
        assert prices == pytest.approx([0.40, 0.41, 0.42])

    async def test_get_market_ids_returns_unique_markets(self, store: PriceStore) -> None:
        await store.append_snapshot(_snap("m1", "2026-01-15T12:00:00"))
        await store.append_snapshot(_snap("m2", "2026-01-15T12:00:00"))
        await store.append_snapshot(_snap("m1", "2026-01-15T12:01:00"))

        ids = await store.get_market_ids()
        assert sorted(ids) == ["m1", "m2"]

    async def test_count_snapshots(self, store: PriceStore) -> None:
        for i in range(5):
            await store.append_snapshot(_snap("0xabc", f"2026-01-15T12:{i:02d}:00"))
        assert await store.count_snapshots("0xabc") == 5
        assert await store.count_snapshots("nonexistent") == 0

    async def test_close_is_idempotent(self) -> None:
        s = PriceStore(path=None)
        await s.append_snapshot(_snap())
        await s.close()
        await s.close()  # second close should not raise

    async def test_read_after_close_raises(self) -> None:
        s = PriceStore(path=None)
        await s.close()
        with pytest.raises(RuntimeError, match="closed"):
            await s.append_snapshot(_snap())

    async def test_date_range_filtering_start(self, store: PriceStore) -> None:
        s1 = _snap("0xabc", "2026-01-15T12:00:00")
        s2 = _snap("0xabc", "2026-01-15T12:01:00")
        s3 = _snap("0xabc", "2026-01-15T12:02:00")
        for s in (s1, s2, s3):
            await store.append_snapshot(s)

        result = []
        async for snap in store.read_snapshots("0xabc", start="2026-01-15T12:01:00"):
            result.append(snap.timestamp)
        assert result == [
            datetime.fromisoformat("2026-01-15T12:01:00"),
            datetime.fromisoformat("2026-01-15T12:02:00"),
        ]

    async def test_date_range_filtering_end(self, store: PriceStore) -> None:
        s1 = _snap("0xabc", "2026-01-15T12:00:00")
        s2 = _snap("0xabc", "2026-01-15T12:01:00")
        s3 = _snap("0xabc", "2026-01-15T12:02:00")
        for s in (s1, s2, s3):
            await store.append_snapshot(s)

        result = []
        async for snap in store.read_snapshots("0xabc", end="2026-01-15T12:01:00"):
            result.append(snap.timestamp)
        assert result == [
            datetime.fromisoformat("2026-01-15T12:00:00"),
            datetime.fromisoformat("2026-01-15T12:01:00"),
        ]

    async def test_date_range_filtering_both(self, store: PriceStore) -> None:
        s1 = _snap("0xabc", "2026-01-15T12:00:00")
        s2 = _snap("0xabc", "2026-01-15T12:01:00")
        s3 = _snap("0xabc", "2026-01-15T12:02:00")
        for s in (s1, s2, s3):
            await store.append_snapshot(s)

        result = []
        async for snap in store.read_snapshots(
            "0xabc", start="2026-01-15T12:00:30", end="2026-01-15T12:01:30"
        ):
            result.append(snap.timestamp)
        assert result == [datetime.fromisoformat("2026-01-15T12:01:00")]

    async def test_read_snapshots_batch_respects_limit(self, store: PriceStore) -> None:
        for i in range(10):
            await store.append_snapshot(_snap("0xabc", f"2026-01-15T12:{i:02d}:00"))
        snaps = await store.read_snapshots_batch("0xabc", limit=3)
        assert len(snaps) == 3

    async def test_empty_store_returns_empty(self, store: PriceStore) -> None:
        assert await store.read_snapshots_batch("nonexistent") == []
        assert await store.count_snapshots("nonexistent") == 0
        assert await store.get_market_ids() == []


# ── JSONL-backed store tests ────────────────────────────────────────────


class TestPriceStoreJsonl:
    @pytest.fixture
    async def store(self, tmp_path) -> PriceStore:
        s = PriceStore(path=str(tmp_path))
        yield s
        await s.close()

    async def test_append_and_read_batch(self, store: PriceStore) -> None:
        s1 = _snap("0xabc", "2026-01-15T12:00:00")
        s2 = _snap("0xabc", "2026-01-15T12:01:00")
        await store.append_snapshot(s1)
        await store.append_snapshot(s2)

        snaps = await store.read_snapshots_batch("0xabc")
        assert len(snaps) == 2
        assert snaps[0].bid_price == 0.40
        assert snaps[1].bid_price == 0.40

    async def test_multiple_markets_separate_files(self, store: PriceStore) -> None:
        await store.append_snapshot(_snap("m1", "2026-01-15T12:00:00"))
        await store.append_snapshot(_snap("m2", "2026-01-15T12:00:00"))
        assert len(await store.read_snapshots_batch("m1")) == 1
        assert len(await store.read_snapshots_batch("m2")) == 1

    async def test_get_market_ids_jsonl(self, store: PriceStore) -> None:
        await store.append_snapshot(_snap("m1"))
        await store.append_snapshot(_snap("m2"))
        ids = await store.get_market_ids()
        assert sorted(ids) == ["m1", "m2"]

    async def test_count_snapshots_jsonl(self, store: PriceStore) -> None:
        for i in range(3):
            await store.append_snapshot(_snap("m1", f"2026-01-15T12:{i:02d}:00"))
        assert await store.count_snapshots("m1") == 3

    # ── Coverage: file not exists paths (lines 79, 108) ──

    async def test_read_batch_nonexistent_market_jsonl(self, store: PriceStore) -> None:
        """read_snapshots_batch for a market with no JSONL file returns []."""
        snaps = await store.read_snapshots_batch("nonexistent")
        assert snaps == []

    async def test_count_snapshots_nonexistent_market_jsonl(self, store: PriceStore) -> None:
        """count_snapshots for a market with no JSONL file returns 0."""
        count = await store.count_snapshots("nonexistent")
        assert count == 0


# ── DuckDB-backed store tests ────────────────────────────────────────────


class TestPriceStoreDuckdb:
    """Tests for the DuckDB backend of PriceStore."""

    @pytest.fixture
    async def mem_store(self) -> PriceStore:
        """In-memory DuckDB store."""
        pytest.importorskip("duckdb")
        s = PriceStore(backend="duckdb")
        yield s
        await s.close()

    @pytest.fixture
    async def file_store(self, tmp_path) -> PriceStore:
        """File-based DuckDB store."""
        pytest.importorskip("duckdb")
        s = PriceStore(path=str(tmp_path), backend="duckdb")
        yield s
        await s.close()

    async def test_append_and_read_batch(self, mem_store: PriceStore) -> None:
        s1 = _snap("0xabc", "2026-01-15T12:00:00")
        s2 = _snap("0xabc", "2026-01-15T12:01:00")
        await mem_store.append_snapshot(s1)
        await mem_store.append_snapshot(s2)

        snaps = await mem_store.read_snapshots_batch("0xabc")
        assert len(snaps) == 2
        assert snaps[0].bid_price == 0.40
        assert snaps[1].bid_price == 0.40

    async def test_read_snapshots_generator(self, mem_store: PriceStore) -> None:
        ts = ["2026-01-15T12:00:00", "2026-01-15T12:01:00", "2026-01-15T12:02:00"]
        for i, t in enumerate(ts):
            await mem_store.append_snapshot(
                _snap("0xabc", t, bid=0.40 + i * 0.01, ask=0.60 + i * 0.01)
            )

        prices = [s.bid_price async for s in mem_store.read_snapshots("0xabc")]
        assert prices == pytest.approx([0.40, 0.41, 0.42])

    async def test_get_market_ids(self, mem_store: PriceStore) -> None:
        await mem_store.append_snapshot(_snap("m1"))
        await mem_store.append_snapshot(_snap("m2"))
        ids = await mem_store.get_market_ids()
        assert sorted(ids) == ["m1", "m2"]

    async def test_count_snapshots(self, mem_store: PriceStore) -> None:
        for i in range(5):
            await mem_store.append_snapshot(_snap("0xabc", f"2026-01-15T12:{i:02d}:00"))
        assert await mem_store.count_snapshots("0xabc") == 5
        assert await mem_store.count_snapshots("nonexistent") == 0

    async def test_read_batch_limit(self, mem_store: PriceStore) -> None:
        for i in range(10):
            await mem_store.append_snapshot(_snap("0xabc", f"2026-01-15T12:{i:02d}:00"))
        snaps = await mem_store.read_snapshots_batch("0xabc", limit=3)
        assert len(snaps) == 3

    async def test_date_filtering_start(self, mem_store: PriceStore) -> None:
        await mem_store.append_snapshot(_snap("0xabc", "2026-01-15T12:00:00"))
        await mem_store.append_snapshot(_snap("0xabc", "2026-01-15T12:01:00"))
        await mem_store.append_snapshot(_snap("0xabc", "2026-01-15T12:02:00"))

        result = [s async for s in mem_store.read_snapshots("0xabc", start="2026-01-15T12:01:00")]
        assert len(result) == 2
        assert result[0].timestamp == datetime.fromisoformat("2026-01-15T12:01:00")

    async def test_date_filtering_end(self, mem_store: PriceStore) -> None:
        await mem_store.append_snapshot(_snap("0xabc", "2026-01-15T12:00:00"))
        await mem_store.append_snapshot(_snap("0xabc", "2026-01-15T12:01:00"))
        await mem_store.append_snapshot(_snap("0xabc", "2026-01-15T12:02:00"))

        result = [s async for s in mem_store.read_snapshots("0xabc", end="2026-01-15T12:01:00")]
        assert len(result) == 2

    async def test_date_filtering_both(self, mem_store: PriceStore) -> None:
        for t in ["2026-01-15T12:00:00", "2026-01-15T12:01:00", "2026-01-15T12:02:00"]:
            await mem_store.append_snapshot(_snap("0xabc", t))

        result = [
            s
            async for s in mem_store.read_snapshots(
                "0xabc", start="2026-01-15T12:00:30", end="2026-01-15T12:01:30"
            )
        ]
        assert len(result) == 1
        assert result[0].timestamp == datetime.fromisoformat("2026-01-15T12:01:00")

    async def test_file_based_store(self, file_store: PriceStore) -> None:
        await file_store.append_snapshot(_snap("0xabc", "2026-01-15T12:00:00"))
        await file_store.append_snapshot(_snap("0xdef", "2026-01-15T12:01:00"))
        assert len(await file_store.read_snapshots_batch("0xabc")) == 1
        assert await file_store.count_snapshots("0xdef") == 1
        assert await file_store.count_snapshots("nonexistent") == 0

    async def test_close_duckdb(self, mem_store: PriceStore) -> None:
        await mem_store.close()
        assert mem_store._closed is True
        with pytest.raises(RuntimeError, match="closed"):
            await mem_store.append_snapshot(_snap())

    async def test_empty_store(self, mem_store: PriceStore) -> None:
        assert await mem_store.get_market_ids() == []
        assert await mem_store.count_snapshots("x") == 0
        assert await mem_store.read_snapshots_batch("x") == []


class TestRowToSnapshot:
    """_row_to_snapshot with string timestamp (line 230)."""

    def test_string_timestamp(self) -> None:
        from polymind.storage.price_store import _row_to_snapshot

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
        row = ("0xabc", "2026-01-15 12:00:00", 0.4, 0.5, 0.45, 100.0, 100.0, 1000.0, "test")
        snap = _row_to_snapshot(row, columns)
        assert snap.market_id == "0xabc"
        assert snap.bid_price == 0.4
        assert snap.source == "test"
