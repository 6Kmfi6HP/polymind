"""
Tests for DuckDBPanelStore — SQL-queryable market data warehouse.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.storage.duckdb_panels import (
    DuckDBConfig,
    DuckDBPanelStore,
)


@pytest.fixture
async def store() -> DuckDBPanelStore:
    s = DuckDBPanelStore(DuckDBConfig(path=":memory:"))
    await s.connect()
    yield s
    await s.close()


class TestDuckDBPanelStore:
    # ── Coverage: _require_conn when not connected (line 102) ──

    async def test_require_conn_raises_when_not_connected(self):
        """Calling any method before connect() raises RuntimeError."""
        s = DuckDBPanelStore(DuckDBConfig(path=":memory:"))
        with pytest.raises(RuntimeError, match="not connected"):
            await s.append_price("mkt1", datetime.now(), 0.45, 0.55, 0.50)
        await s.close()

    async def test_connect_creates_tables(self, store: DuckDBPanelStore):
        """Connect should create the schema without error."""
        result = await store.get_market_list()
        assert result == []

    async def test_append_and_query_price(self, store: DuckDBPanelStore):
        ts = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
        await store.append_price("mkt1", ts, 0.45, 0.55, 0.50)
        prices = await store.query_prices("mkt1")
        assert len(prices) == 1
        assert prices[0]["market_id"] == "mkt1"
        assert prices[0]["bid_price"] == 0.45
        assert prices[0]["ask_price"] == 0.55

    async def test_query_with_time_filter(self, store: DuckDBPanelStore):
        ts1 = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 7, 4, 13, 0, 0, tzinfo=timezone.utc)
        await store.append_price("mkt1", ts1, 0.45, 0.55, 0.50)
        await store.append_price("mkt1", ts2, 0.46, 0.56, 0.51)

        filtered = await store.query_prices("mkt1", start="2026-07-04T12:30:00Z")
        assert len(filtered) == 1
        assert filtered[0]["bid_price"] == 0.46

    async def test_multiple_markets(self, store: DuckDBPanelStore):
        ts = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
        await store.append_price("mkt1", ts, 0.45, 0.55, 0.50)
        await store.append_price("mkt2", ts, 0.40, 0.50, 0.45)

        markets = await store.get_market_list()
        assert sorted(markets) == ["mkt1", "mkt2"]

    async def test_count_prices(self, store: DuckDBPanelStore):
        ts = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            await store.append_price("mkt1", ts, 0.45 + i * 0.01, 0.55 + i * 0.01, 0.50 + i * 0.01)
        count = await store.count_prices("mkt1")
        assert count == 5

    async def test_register_and_get_metadata(self, store: DuckDBPanelStore):
        await store.register_market("mkt1", question="Will BTC hit 100k?")
        meta = await store.get_metadata("mkt1")
        assert meta is not None
        assert meta["question"] == "Will BTC hit 100k?"
        assert meta["outcome_a"] == "YES"

    async def test_get_metadata_nonexistent(self, store: DuckDBPanelStore):
        meta = await store.get_metadata("nonexistent")
        assert meta is None

    async def test_store_and_query_factor_scores(self, store: DuckDBPanelStore):
        ts = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
        await store.store_factor_score("mkt1", "momentum_7d", 0.85, ts)
        await store.store_factor_score("mkt2", "momentum_7d", 0.72, ts)
        await store.store_factor_score("mkt3", "momentum_7d", 0.91, ts)

        scores = await store.query_factor_scores("momentum_7d", limit=2)
        assert len(scores) == 2
        # Ordered by score DESC
        assert scores[0]["market_id"] == "mkt3"
        assert scores[0]["score"] == 0.91

    async def test_get_market_summary(self, store: DuckDBPanelStore):
        ts = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
        await store.append_price("mkt1", ts, 0.45, 0.55, 0.50)
        await store.append_price("mkt1", ts, 0.46, 0.56, 0.51)

        summary = await store.get_market_summary("mkt1")
        assert summary["num_observations"] == 2
        assert summary["avg_mid"] == 0.505
        assert summary["avg_spread"] == pytest.approx(0.10, abs=1e-6)  # ask-bid

    async def test_append_prices_batch(self, store: DuckDBPanelStore):
        ts = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
        rows = [
            {
                "market_id": "mkt1",
                "timestamp": ts,
                "bid_price": 0.45,
                "ask_price": 0.55,
                "mid_price": 0.50,
            },
            {
                "market_id": "mkt1",
                "timestamp": ts,
                "bid_price": 0.46,
                "ask_price": 0.56,
                "mid_price": 0.51,
            },
        ]
        await store.append_prices_batch(rows)
        count = await store.count_prices("mkt1")
        assert count == 2

    async def test_empty_query(self, store: DuckDBPanelStore):
        prices = await store.query_prices("nonexistent")
        assert prices == []

    async def test_query_with_end_filter(self, store: DuckDBPanelStore):
        """query_prices with end parameter filters correctly (lines 183-184)."""
        ts1 = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 7, 4, 13, 0, 0, tzinfo=timezone.utc)
        await store.append_price("mkt1", ts1, 0.45, 0.55, 0.50)
        await store.append_price("mkt1", ts2, 0.46, 0.56, 0.51)

        filtered = await store.query_prices("mkt1", end="2026-07-04T12:30:00Z")
        assert len(filtered) == 1
        assert filtered[0]["bid_price"] == 0.45

    async def test_query_with_start_and_end(self, store: DuckDBPanelStore):
        """query_prices with both start and end filters."""
        ts1 = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 7, 4, 13, 0, 0, tzinfo=timezone.utc)
        ts3 = datetime(2026, 7, 4, 14, 0, 0, tzinfo=timezone.utc)
        await store.append_price("mkt1", ts1, 0.45, 0.55, 0.50)
        await store.append_price("mkt1", ts2, 0.46, 0.56, 0.51)
        await store.append_price("mkt1", ts3, 0.47, 0.57, 0.52)

        filtered = await store.query_prices(
            "mkt1", start="2026-07-04T12:30:00Z", end="2026-07-04T13:30:00Z"
        )
        assert len(filtered) == 1
        assert filtered[0]["bid_price"] == 0.46

    async def test_empty_summary(self, store: DuckDBPanelStore):
        summary = await store.get_market_summary("nonexistent")
        assert summary == {}
