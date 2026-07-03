"""
Tests for backtesting data loading.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.backtesting.data import (
    BacktestDataConfig,
    DataLoader,
    DataSource,
    MarketDataPoint,
)


class TestDataSource:
    def test_enum_values(self):
        assert isinstance(DataSource.JSONL, DataSource)
        assert isinstance(DataSource.CSV, DataSource)
        assert isinstance(DataSource.DUCKDB, DataSource)
        assert isinstance(DataSource.IN_MEMORY, DataSource)

    def test_enum_members(self):
        names = {m.name for m in DataSource}
        assert names == {"JSONL", "CSV", "DUCKDB", "IN_MEMORY"}


class TestBacktestDataConfig:
    def test_minimal_construction(self):
        config = BacktestDataConfig(source=DataSource.IN_MEMORY)
        assert config.source == DataSource.IN_MEMORY
        assert config.path == ""
        assert config.start_date is None
        assert config.end_date is None
        assert config.market_ids is None

    def test_full_construction(self):
        config = BacktestDataConfig(
            source=DataSource.JSONL,
            path="/tmp/data.jsonl",
            start_date="2025-01-01",
            end_date="2025-12-31",
            market_ids=["0xabc", "0xdef"],
        )
        assert config.source == DataSource.JSONL
        assert config.path == "/tmp/data.jsonl"
        assert config.start_date == "2025-01-01"
        assert config.end_date == "2025-12-31"
        assert config.market_ids == ["0xabc", "0xdef"]

    def test_immutable_fields(self):
        config = BacktestDataConfig(source=DataSource.DUCKDB, path="test.db")
        assert config.source == DataSource.DUCKDB
        assert config.path == "test.db"


class TestMarketDataPoint:
    def test_construction(self):
        ts = datetime(2025, 6, 1, 12, 0, 0)
        dp = MarketDataPoint(
            market_id="0x123",
            timestamp=ts,
            bid_price=0.45,
            ask_price=0.55,
            mid_price=0.50,
            bid_size=100.0,
            ask_size=200.0,
            volume=5000.0,
        )
        assert dp.market_id == "0x123"
        assert dp.timestamp == ts
        assert dp.bid_price == 0.45
        assert dp.ask_price == 0.55
        assert dp.mid_price == 0.50
        assert dp.bid_size == 100.0
        assert dp.ask_size == 200.0
        assert dp.volume == 5000.0

    def test_to_market_snapshot(self):
        ts = datetime(2025, 6, 1, 12, 0, 0)
        dp = MarketDataPoint(
            market_id="0x123",
            timestamp=ts,
            bid_price=0.45,
            ask_price=0.55,
            mid_price=0.50,
            bid_size=100.0,
            ask_size=200.0,
            volume=5000.0,
        )
        snap = dp.to_market_snapshot()
        assert snap.market_id == "0x123"
        assert snap.bid_price == 0.45
        assert snap.ask_price == 0.55
        assert snap.mid_price == 0.50
        assert snap.bid_size == 100.0
        assert snap.ask_size == 200.0
        assert snap.timestamp == ts


class TestDataLoader:
    def _make_points(self) -> list[MarketDataPoint]:
        return [
            MarketDataPoint(
                market_id="0xaaa",
                timestamp=datetime(2025, 1, 1, 10, 0, 0),
                bid_price=0.40,
                ask_price=0.50,
                mid_price=0.45,
                bid_size=100.0,
                ask_size=100.0,
                volume=1000.0,
            ),
            MarketDataPoint(
                market_id="0xbbb",
                timestamp=datetime(2025, 1, 1, 10, 0, 0),
                bid_price=0.60,
                ask_price=0.70,
                mid_price=0.65,
                bid_size=200.0,
                ask_size=200.0,
                volume=2000.0,
            ),
            MarketDataPoint(
                market_id="0xaaa",
                timestamp=datetime(2025, 6, 1, 10, 0, 0),
                bid_price=0.42,
                ask_price=0.52,
                mid_price=0.47,
                bid_size=150.0,
                ask_size=150.0,
                volume=3000.0,
            ),
        ]

    @pytest.mark.asyncio
    async def test_load_snapshots_in_memory_no_filter(self):
        points = self._make_points()
        loader = DataLoader(points)
        config = BacktestDataConfig(source=DataSource.IN_MEMORY)

        results = await loader.load_snapshots_batch(config)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_load_snapshots_in_memory_with_date_filter(self):
        points = self._make_points()
        loader = DataLoader(points)
        config = BacktestDataConfig(
            source=DataSource.IN_MEMORY,
            start_date="2025-03-01",
            end_date="2025-12-31",
        )

        results = await loader.load_snapshots_batch(config)
        assert len(results) == 1
        assert results[0].market_id == "0xaaa"
        assert results[0].timestamp == datetime(2025, 6, 1, 10, 0, 0)

    @pytest.mark.asyncio
    async def test_load_snapshots_in_memory_with_market_filter(self):
        points = self._make_points()
        loader = DataLoader(points)
        config = BacktestDataConfig(
            source=DataSource.IN_MEMORY,
            market_ids=["0xbbb"],
        )

        results = await loader.load_snapshots_batch(config)
        assert len(results) == 1
        assert results[0].market_id == "0xbbb"

    @pytest.mark.asyncio
    async def test_load_snapshots_in_memory_no_data(self):
        loader = DataLoader()
        config = BacktestDataConfig(source=DataSource.IN_MEMORY)

        results = await loader.load_snapshots_batch(config)
        assert results == []

    @pytest.mark.asyncio
    async def test_load_snapshots_in_memory_with_combined_filters(self):
        points = self._make_points()
        loader = DataLoader(points)
        config = BacktestDataConfig(
            source=DataSource.IN_MEMORY,
            start_date="2025-01-01",
            end_date="2025-01-31",
            market_ids=["0xaaa"],
        )

        results = await loader.load_snapshots_batch(config)
        assert len(results) == 1
        assert results[0].market_id == "0xaaa"
        assert results[0].timestamp == datetime(2025, 1, 1, 10, 0, 0)

    @pytest.mark.asyncio
    async def test_get_market_ids(self):
        points = self._make_points()
        loader = DataLoader(points)
        config = BacktestDataConfig(source=DataSource.IN_MEMORY)

        ids = await loader.get_market_ids(config)
        assert ids == ["0xaaa", "0xbbb"]

    @pytest.mark.asyncio
    async def test_get_market_ids_with_filter(self):
        points = self._make_points()
        loader = DataLoader(points)
        config = BacktestDataConfig(
            source=DataSource.IN_MEMORY,
            start_date="2025-06-01",
        )

        ids = await loader.get_market_ids(config)
        assert ids == ["0xaaa"]

    @pytest.mark.asyncio
    async def test_load_snapshots_async_generator(self):
        points = self._make_points()
        loader = DataLoader(points)
        config = BacktestDataConfig(source=DataSource.IN_MEMORY)

        count = 0
        async for _ in loader.load_snapshots(config):
            count += 1
        assert count == 3

    @pytest.mark.asyncio
    async def test_load_in_memory_replaces_data(self):
        initial = [
            MarketDataPoint(
                market_id="0x111",
                timestamp=datetime(2025, 1, 1, 0, 0, 0),
                bid_price=0.1,
                ask_price=0.2,
                mid_price=0.15,
                bid_size=10.0,
                ask_size=10.0,
                volume=100.0,
            ),
        ]
        replacement = [
            MarketDataPoint(
                market_id="0x222",
                timestamp=datetime(2025, 1, 1, 0, 0, 0),
                bid_price=0.3,
                ask_price=0.4,
                mid_price=0.35,
                bid_size=20.0,
                ask_size=20.0,
                volume=200.0,
            ),
        ]
        loader = DataLoader(initial)

        # Before load_in_memory
        ids1 = await loader.get_market_ids(
            BacktestDataConfig(source=DataSource.IN_MEMORY)
        )
        assert ids1 == ["0x111"]

        loader.load_in_memory(replacement)

        # After load_in_memory
        ids2 = await loader.get_market_ids(
            BacktestDataConfig(source=DataSource.IN_MEMORY)
        )
        assert ids2 == ["0x222"]
