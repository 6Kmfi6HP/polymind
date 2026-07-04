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
        ids1 = await loader.get_market_ids(BacktestDataConfig(source=DataSource.IN_MEMORY))
        assert ids1 == ["0x111"]

        loader.load_in_memory(replacement)

        # After load_in_memory
        ids2 = await loader.get_market_ids(BacktestDataConfig(source=DataSource.IN_MEMORY))
        assert ids2 == ["0x222"]

    # ------------------------------------------------------------------
    # File-based data source tests (raise coverage on data.py)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_load_snapshots_jsonl(self, tmp_path):
        """Load from a newline-delimited JSON file."""
        f = tmp_path / "data.jsonl"
        f.write_text(
            '{"market_id":"m1","timestamp":"2025-06-01T10:00:00","bid_price":0.4,"ask_price":0.5,"mid_price":0.45,"bid_size":100,"ask_size":100,"volume":1000}\n'
            '{"market_id":"m2","timestamp":"2025-06-01T11:00:00","bid_price":0.6,"ask_price":0.7,"mid_price":0.65,"bid_size":200,"ask_size":200,"volume":2000}\n'
        )
        loader = DataLoader()
        config = BacktestDataConfig(source=DataSource.JSONL, path=str(f))
        results = await loader.load_snapshots_batch(config)
        assert len(results) == 2
        assert results[0].market_id == "m1"
        assert results[1].market_id == "m2"

    @pytest.mark.asyncio
    async def test_load_snapshots_jsonl_with_filter(self, tmp_path):
        """Load from JSONL with date and market filtering."""
        f = tmp_path / "data.jsonl"
        f.write_text(
            '{"market_id":"m1","timestamp":"2025-06-01T10:00:00","bid_price":0.4,"ask_price":0.5,"mid_price":0.45,"bid_size":100,"ask_size":100,"volume":1000}\n'
            '{"market_id":"m2","timestamp":"2025-06-02T10:00:00","bid_price":0.6,"ask_price":0.7,"mid_price":0.65,"bid_size":200,"ask_size":200,"volume":2000}\n'
            '{"market_id":"m1","timestamp":"2025-07-01T10:00:00","bid_price":0.4,"ask_price":0.5,"mid_price":0.45,"bid_size":100,"ask_size":100,"volume":1000}\n'
        )
        loader = DataLoader()
        config = BacktestDataConfig(
            source=DataSource.JSONL,
            path=str(f),
            start_date="2025-06-01",
            end_date="2025-06-30",
            market_ids=["m1"],
        )
        results = await loader.load_snapshots_batch(config)
        assert len(results) == 1
        assert results[0].market_id == "m1"

    @pytest.mark.asyncio
    async def test_load_snapshots_jsonl_empty_lines(self, tmp_path):
        """JSONL with blank lines should be skipped."""
        f = tmp_path / "data.jsonl"
        f.write_text(
            '{"market_id":"m1","timestamp":"2025-06-01T10:00:00","bid_price":0.4,"ask_price":0.5,"mid_price":0.45,"bid_size":100,"ask_size":100,"volume":1000}\n'
            "\n"
            '{"market_id":"m2","timestamp":"2025-06-01T11:00:00","bid_price":0.6,"ask_price":0.7,"mid_price":0.65,"bid_size":200,"ask_size":200,"volume":2000}\n'
        )
        loader = DataLoader()
        config = BacktestDataConfig(source=DataSource.JSONL, path=str(f))
        results = await loader.load_snapshots_batch(config)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_load_snapshots_csv(self, tmp_path):
        """Load from a CSV file."""
        f = tmp_path / "data.csv"
        f.write_text(
            "market_id,timestamp,bid_price,ask_price,mid_price,bid_size,ask_size,volume\n"
            "m1,2025-06-01T10:00:00,0.4,0.5,0.45,100,100,1000\n"
            "m2,2025-06-01T11:00:00,0.6,0.7,0.65,200,200,2000\n"
        )
        loader = DataLoader()
        config = BacktestDataConfig(source=DataSource.CSV, path=str(f))
        results = await loader.load_snapshots_batch(config)
        assert len(results) == 2
        assert results[0].market_id == "m1"
        assert results[1].market_id == "m2"

    @pytest.mark.asyncio
    async def test_load_snapshots_csv_with_filter(self, tmp_path):
        """Load from CSV with market filter."""
        f = tmp_path / "data.csv"
        f.write_text(
            "market_id,timestamp,bid_price,ask_price,mid_price,bid_size,ask_size,volume\n"
            "m1,2025-06-01T10:00:00,0.4,0.5,0.45,100,100,1000\n"
            "m2,2025-06-01T11:00:00,0.6,0.7,0.65,200,200,2000\n"
        )
        loader = DataLoader()
        config = BacktestDataConfig(
            source=DataSource.CSV,
            path=str(f),
            market_ids=["m2"],
        )
        results = await loader.load_snapshots_batch(config)
        assert len(results) == 1
        assert results[0].market_id == "m2"

    @pytest.mark.asyncio
    async def test_load_snapshots_duckdb(self, tmp_path):
        """Load data from a DuckDB database."""
        pytest.importorskip("duckdb")
        import duckdb

        db = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db))
        conn.execute(
            "CREATE TABLE market_data ("
            "  market_id VARCHAR, timestamp TIMESTAMP, bid_price DOUBLE, ask_price DOUBLE,"
            "  mid_price DOUBLE, bid_size DOUBLE, ask_size DOUBLE, volume DOUBLE)"
        )
        conn.execute(
            "INSERT INTO market_data VALUES "
            "('m1', '2025-06-01 10:00:00', 0.4, 0.5, 0.45, 100, 100, 1000),"
            "('m2', '2025-06-01 11:00:00', 0.6, 0.7, 0.65, 200, 200, 2000)"
        )
        conn.close()

        loader = DataLoader()
        config = BacktestDataConfig(source=DataSource.DUCKDB, path=str(db))
        results = await loader.load_snapshots_batch(config)
        assert len(results) == 2
        assert results[0].market_id == "m1"
        assert results[1].market_id == "m2"

    @pytest.mark.asyncio
    async def test_load_snapshots_duckdb_with_filter(self, tmp_path):
        """Load from DuckDB with date filter."""
        pytest.importorskip("duckdb")
        import duckdb

        db = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db))
        conn.execute(
            "CREATE TABLE market_data ("
            "  market_id VARCHAR, timestamp TIMESTAMP, bid_price DOUBLE, ask_price DOUBLE,"
            "  mid_price DOUBLE, bid_size DOUBLE, ask_size DOUBLE, volume DOUBLE)"
        )
        conn.execute(
            "INSERT INTO market_data VALUES "
            "('m1', '2025-06-01 10:00:00', 0.4, 0.5, 0.45, 100, 100, 1000),"
            "('m2', '2025-07-01 10:00:00', 0.6, 0.7, 0.65, 200, 200, 2000)"
        )
        conn.close()

        loader = DataLoader()
        config = BacktestDataConfig(
            source=DataSource.DUCKDB,
            path=str(db),
            start_date="2025-06-15",
        )
        results = await loader.load_snapshots_batch(config)
        assert len(results) == 1
        assert results[0].market_id == "m2"

    @pytest.mark.asyncio
    async def test_get_market_ids_jsonl(self, tmp_path):
        """get_market_ids from JSONL source."""
        f = tmp_path / "data.jsonl"
        f.write_text(
            '{"market_id":"m1","timestamp":"2025-06-01T10:00:00","bid_price":0.4,"ask_price":0.5,"mid_price":0.45,"bid_size":100,"ask_size":100,"volume":1000}\n'
            '{"market_id":"m2","timestamp":"2025-06-01T11:00:00","bid_price":0.6,"ask_price":0.7,"mid_price":0.65,"bid_size":200,"ask_size":200,"volume":2000}\n'
        )
        loader = DataLoader()
        config = BacktestDataConfig(source=DataSource.JSONL, path=str(f))
        ids = await loader.get_market_ids(config)
        assert ids == ["m1", "m2"]
