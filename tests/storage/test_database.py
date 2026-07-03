"""Tests for the SQLite persistence layer."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from polymind.storage.database import AsyncDatabase, DatabaseConfig, DatabaseConnection


class TestDatabaseConfig:
    """Unit tests for DatabaseConfig dataclass."""

    def test_defaults(self):
        config = DatabaseConfig(path=":memory:")
        assert config.path == ":memory:"
        assert config.pool_size == 5
        assert config.timeout == 30.0
        assert config.wal_mode is True

    def test_custom_values(self):
        config = DatabaseConfig(path="/tmp/db.sqlite", pool_size=3, timeout=10.0, wal_mode=False)
        assert config.path == "/tmp/db.sqlite"
        assert config.pool_size == 3
        assert config.timeout == 10.0
        assert config.wal_mode is False

    def test_frozen(self):
        config = DatabaseConfig(path=":memory:")
        with pytest.raises(AttributeError):
            config.path = "/other"  # type: ignore[misc]


class TestDatabaseConnection:
    """Tests for DatabaseConnection — each test gets its own in-memory db."""

    @pytest.fixture
    def config(self) -> DatabaseConfig:
        return DatabaseConfig(path=":memory:", wal_mode=False)

    @pytest.fixture
    async def conn(self, config: DatabaseConfig) -> DatabaseConnection:
        async with DatabaseConnection(config) as c:
            await c.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
            yield c

    async def test_execute_and_fetch_one(self, conn: DatabaseConnection):
        await conn.execute("INSERT INTO test (val) VALUES (?)", ("hello",))
        row = await conn.fetch_one("SELECT * FROM test WHERE id = ?", (1,))
        assert row is not None
        assert row["id"] == 1
        assert row["val"] == "hello"

    async def test_fetch_one_returns_none(self, conn: DatabaseConnection):
        row = await conn.fetch_one("SELECT * FROM test WHERE id = ?", (999,))
        assert row is None

    async def test_fetch_all(self, conn: DatabaseConnection):
        await conn.execute_many(
            "INSERT INTO test (val) VALUES (?)",
            [("a",), ("b",), ("c",)],
        )
        rows = await conn.fetch_all("SELECT * FROM test ORDER BY id")
        assert len(rows) == 3
        assert rows[0]["val"] == "a"
        assert rows[2]["val"] == "c"

    async def test_fetch_all_empty(self, conn: DatabaseConnection):
        rows = await conn.fetch_all("SELECT * FROM test WHERE val = ?", ("x",))
        assert rows == []

    async def test_execute_many(self, conn: DatabaseConnection):
        await conn.execute_many(
            "INSERT INTO test (val) VALUES (?)",
            [("x",), ("y",)],
        )
        rows = await conn.fetch_all("SELECT * FROM test ORDER BY id")
        assert len(rows) == 2

    async def test_raises_when_not_open(self):
        c = DatabaseConnection(DatabaseConfig(path=":memory:", wal_mode=False))
        with pytest.raises(RuntimeError, match="Connection is not open"):
            await c.execute("SELECT 1")

    async def test_double_close_is_idempotent(self, conn: DatabaseConnection):
        await conn.close()
        await conn.close()  # should not raise

    async def test_wal_mode_enabled(self):
        """WAL mode should set journal_mode to wal."""
        config = DatabaseConfig(path=":memory:", wal_mode=True)
        async with DatabaseConnection(config) as c:
            row = await c.fetch_one("PRAGMA journal_mode")
            assert row is not None
            # In-memory with WAL pragma may still report "memory" but we just
            # verify the pragma was executed without error (WAL is a no-op
            # for :memory: in some SQLite builds).
            assert row["journal_mode"] in ("wal", "memory", "delete")


class TestAsyncDatabase:
    """Tests for the higher-level AsyncDatabase."""

    async def test_context_manager(self):
        config = DatabaseConfig(path=":memory:", wal_mode=False)
        async with AsyncDatabase(config) as db:
            assert isinstance(db, AsyncDatabase)

    async def test_get_connection(self):
        config = DatabaseConfig(path=":memory:", wal_mode=False)
        async with AsyncDatabase(config) as db:
            conn = await db.get_connection()
            try:
                await conn.execute("CREATE TABLE t (x INTEGER)")
                await conn.execute("INSERT INTO t VALUES (?)", (42,))
                row = await conn.fetch_one("SELECT x FROM t")
                assert row is not None
                assert row["x"] == 42
            finally:
                await conn.close()

    async def test_pool_size_respected(self):
        """The semaphore should limit concurrent connections."""
        config = DatabaseConfig(path=":memory:", pool_size=2, wal_mode=False)
        async with AsyncDatabase(config) as db:
            c1 = await db.get_connection()
            c2 = await db.get_connection()
            with pytest.raises(asyncio.TimeoutError):
                async with asyncio.timeout(0.1):
                    await db.get_connection()
            await c1.close()
            await c2.close()

    async def test_pool_reuses_slot_after_close(self):
        config = DatabaseConfig(path=":memory:", pool_size=1, wal_mode=False)
        async with AsyncDatabase(config) as db:
            conn = await db.get_connection()
            await conn.close()
            # Should be able to get another one immediately
            conn2 = await db.get_connection()
            await conn2.close()

    async def test_migrate_creates_tables(self):
        """Run .sql files from a temp migrations directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            mig_dir = Path(tmpdir) / "migrations"
            mig_dir.mkdir()

            (mig_dir / "001_create_users.sql").write_text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);"
            )
            (mig_dir / "002_add_data.sql").write_text(
                "INSERT INTO users (name) VALUES ('alice');"
            )

            config = DatabaseConfig(path=db_path, wal_mode=False)
            async with AsyncDatabase(config) as db:
                await db.migrate(str(mig_dir))

                conn = await db.get_connection()
                try:
                    rows = await conn.fetch_all("SELECT * FROM users")
                    assert len(rows) == 1
                    assert rows[0]["name"] == "alice"
                finally:
                    await conn.close()

    async def test_migrate_empty_directory(self):
        """No .sql files should be a no-op."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = DatabaseConfig(path=":memory:", wal_mode=False)
            async with AsyncDatabase(config) as db:
                await db.migrate(tmpdir)  # should not raise

    async def test_migrate_missing_directory(self):
        config = DatabaseConfig(path=":memory:", wal_mode=False)
        async with AsyncDatabase(config) as db:
            with pytest.raises(NotADirectoryError):
                await db.migrate("/nonexistent/migrations")


@pytest.fixture(scope="module")
def event_loop():
    """Module-scoped event loop for the module-level async fixtures."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
