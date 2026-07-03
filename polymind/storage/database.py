"""SQLite persistence layer using aiosqlite."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration for the SQLite database connection."""

    path: str
    pool_size: int = 5
    timeout: float = 30.0
    wal_mode: bool = True


class DatabaseConnection:
    """Async context manager wrapping a single aiosqlite connection.

    Typical usage::

        async with DatabaseConnection(config) as db:
            await db.execute("CREATE TABLE ...")
            row = await db.fetch_one("SELECT * FROM ...")
    """

    def __init__(
        self,
        config: DatabaseConfig,
        _release_cb: Any = None,
    ) -> None:
        self._config = config
        self._release_cb = _release_cb
        self._conn: aiosqlite.Connection | None = None

    async def __aenter__(self) -> DatabaseConnection:
        self._conn = await aiosqlite.connect(
            self._config.path,
            timeout=self._config.timeout,
        )
        self._conn.row_factory = aiosqlite.Row
        if self._config.wal_mode:
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA synchronous=NORMAL")
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying connection and release pool slot (if pooled)."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
        if self._release_cb is not None:
            cb = self._release_cb
            self._release_cb = None
            cb()

    def _require_open(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Connection is not open")
        return self._conn

    async def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        """Execute a single SQL statement."""
        conn = self._require_open()
        await conn.execute(sql, params or ())

    async def fetch_one(
        self, sql: str, params: tuple[Any, ...] | None = None
    ) -> dict[str, Any] | None:
        """Execute a query and return one row as a dict, or None."""
        conn = self._require_open()
        cursor = await conn.execute(sql, params or ())
        row = await cursor.fetchone()
        return dict(row) if row is not None else None

    async def fetch_all(
        self, sql: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a query and return all rows as a list of dicts."""
        conn = self._require_open()
        cursor = await conn.execute(sql, params or ())
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def execute_many(self, sql: str, params_list: list[tuple[Any, ...]]) -> None:
        """Execute a statement against every parameter set in *params_list*."""
        conn = self._require_open()
        await conn.executemany(sql, params_list)

    async def commit(self) -> None:
        """Commit the current transaction."""
        conn = self._require_open()
        await conn.commit()


class AsyncDatabase:
    """Higher-level database manager with connection pool and migration support.

    Usage::

        config = DatabaseConfig(path="data.db", pool_size=5)
        async with AsyncDatabase(config) as db:
            await db.migrate("migrations/")
            conn = await db.get_connection()
            try:
                ...
            finally:
                await conn.close()
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._semaphore = asyncio.Semaphore(config.pool_size)

    async def __aenter__(self) -> AsyncDatabase:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass  # Individual connections are managed by the caller

    async def get_connection(self) -> DatabaseConnection:
        """Acquire a database connection from the pool.

        The caller **must** call ``.close()`` on the returned connection
        (or use it as an async context manager) to release the pool slot.
        """
        await self._semaphore.acquire()
        conn = DatabaseConnection(self._config, _release_cb=self._semaphore.release)
        await conn.__aenter__()
        return conn

    async def migrate(self, migrations_dir: str) -> None:
        """Run all ``.sql`` migration files in sorted order.

        Files are executed in lexicographic order (typically
        ``001_…``, ``002_…``). Each file is executed verbatim.
        """
        mig_path = Path(migrations_dir)
        if not mig_path.is_dir():
            raise NotADirectoryError(f"Migrations directory not found: {migrations_dir}")

        sql_files = sorted(mig_path.glob("*.sql"))
        if not sql_files:
            return

        conn = await self.get_connection()
        try:
            for sql_file in sql_files:
                sql = sql_file.read_text()
                await conn.execute(sql)
            await conn.commit()
        finally:
            await conn.close()
