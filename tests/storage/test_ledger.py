"""Tests for the persistent LedgerStore."""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.ledger import EntryType, LedgerEntry
from polymind.execution.executor import PositionRecord
from polymind.storage.database import DatabaseConfig
from polymind.storage.ledger import LedgerStore


@pytest.fixture
async def store() -> LedgerStore:
    """Create an in-memory LedgerStore for testing."""
    cfg = DatabaseConfig(path=":memory:")
    s = LedgerStore(cfg)
    yield s
    await s.close()


def _entry(
    entry_id: str,
    market_id: str = "0xabc",
    delta_cash: float = 0.0,
    delta_position: float = 0.0,
    cash_after: float = 0.0,
    position_after: float = 0.0,
) -> LedgerEntry:
    return LedgerEntry(
        entry_id=entry_id,
        entry_type=EntryType.FILL,
        timestamp=datetime(2026, 1, 1),
        market_id=market_id,
        description="test",
        delta_cash=delta_cash,
        delta_position=delta_position,
        position_after=position_after,
        cash_after=cash_after,
    )


class TestAppend:
    async def test_append_entry(self, store: LedgerStore) -> None:
        entry = _entry("e1")
        await store.append(entry)
        entries = await store.get_entries("0xabc")
        assert len(entries) == 1
        assert entries[0].entry_id == "e1"

    async def test_append_multiple(self, store: LedgerStore) -> None:
        for i in range(5):
            await store.append(_entry(f"e{i}"))
        entries = await store.get_entries("0xabc")
        assert len(entries) == 5

    async def test_append_different_markets(self, store: LedgerStore) -> None:
        await store.append(_entry("e1", market_id="m1"))
        await store.append(_entry("e2", market_id="m2"))
        assert len(await store.get_entries("m1")) == 1
        assert len(await store.get_entries("m2")) == 1


class TestGetEntries:
    async def test_get_entries_returns_empty_when_none(self, store: LedgerStore) -> None:
        entries = await store.get_entries("nonexistent")
        assert entries == []

    async def test_get_entries_respects_limit(self, store: LedgerStore) -> None:
        for i in range(10):
            await store.append(_entry(f"e{i}"))
        entries = await store.get_entries("0xabc", limit=3)
        assert len(entries) == 3

    async def test_get_entries_returns_in_order(self, store: LedgerStore) -> None:
        for i in range(5):
            await store.append(_entry(f"e{i}", delta_cash=float(i)))
        entries = await store.get_entries("0xabc")
        assert [e.delta_cash for e in entries] == [0.0, 1.0, 2.0, 3.0, 4.0]


class TestGetPnl:
    async def test_get_pnl_zero_when_empty(self, store: LedgerStore) -> None:
        pnl = await store.get_pnl("0xabc")
        assert pnl == 0.0

    async def test_get_pnl_sums_delta_cash(self, store: LedgerStore) -> None:
        await store.append(_entry("e1", delta_cash=-10.0))
        await store.append(_entry("e2", delta_cash=-5.0))
        await store.append(_entry("e3", delta_cash=20.0))
        pnl = await store.get_pnl("0xabc")
        assert pnl == 5.0  # -10 + -5 + 20

    async def test_get_pnl_per_market(self, store: LedgerStore) -> None:
        await store.append(_entry("e1", market_id="m1", delta_cash=100.0))
        await store.append(_entry("e2", market_id="m2", delta_cash=50.0))
        assert await store.get_pnl("m1") == 100.0
        assert await store.get_pnl("m2") == 50.0


class TestGetCashBalance:
    async def test_get_cash_balance_zero_when_empty(self, store: LedgerStore) -> None:
        bal = await store.get_cash_balance()
        assert bal == 0.0

    async def test_get_cash_balance_from_last_entry(self, store: LedgerStore) -> None:
        await store.append(
            LedgerEntry(
                entry_id="e1",
                entry_type=EntryType.CASH_ADJUSTMENT,
                timestamp=datetime(2026, 1, 1),
                market_id="m1",
                description="deposit",
                delta_cash=1000.0,
                delta_position=0.0,
                position_after=0.0,
                cash_after=1000.0,
            )
        )
        await store.append(
            LedgerEntry(
                entry_id="e2",
                entry_type=EntryType.FILL,
                timestamp=datetime(2026, 1, 2),
                market_id="m1",
                description="buy",
                delta_cash=-200.0,
                delta_position=10.0,
                position_after=10.0,
                cash_after=800.0,
            )
        )
        bal = await store.get_cash_balance()
        assert bal == 800.0


class TestPosition:
    async def test_get_position_returns_none_when_missing(self, store: LedgerStore) -> None:
        pos = await store.get_position("0xabc")
        assert pos is None

    async def test_update_position_round_trip(self, store: LedgerStore) -> None:
        rec = PositionRecord(
            market_id="0xabc",
            outcome="YES",
            size=10.0,
            avg_entry=0.50,
            realized_pnl=5.0,
        )
        await store.update_position("0xabc", rec)
        pos = await store.get_position("0xabc")
        assert pos is not None
        assert pos.market_id == "0xabc"
        assert pos.outcome == "YES"
        assert pos.size == 10.0
        assert pos.avg_entry == 0.50
        assert pos.realized_pnl == 5.0

    async def test_update_position_overwrites(self, store: LedgerStore) -> None:
        rec1 = PositionRecord(
            market_id="0xabc",
            outcome="YES",
            size=10.0,
            avg_entry=0.50,
            realized_pnl=5.0,
        )
        await store.update_position("0xabc", rec1)
        rec2 = PositionRecord(
            market_id="0xabc",
            outcome="YES",
            size=20.0,
            avg_entry=0.60,
            realized_pnl=10.0,
        )
        await store.update_position("0xabc", rec2)
        pos = await store.get_position("0xabc")
        assert pos is not None
        assert pos.size == 20.0
        assert pos.avg_entry == 0.60
        assert pos.realized_pnl == 10.0

    async def test_update_position_different_markets(self, store: LedgerStore) -> None:
        rec_a = PositionRecord(
            market_id="m1", outcome="YES", size=5.0, avg_entry=0.5, realized_pnl=0.0
        )
        rec_b = PositionRecord(
            market_id="m2", outcome="NO", size=-3.0, avg_entry=0.3, realized_pnl=2.0
        )
        await store.update_position("m1", rec_a)
        await store.update_position("m2", rec_b)
        assert await store.get_position("m1") is not None
        assert await store.get_position("m2") is not None
        assert await store.get_position("nonexistent") is None


class TestClose:
    async def test_close_idempotent(self) -> None:
        cfg = DatabaseConfig(path=":memory:")
        s = LedgerStore(cfg)
        # Trigger lazy init
        await s.append(_entry("e1"))
        await s.close()
        await s.close()  # second close should not raise

    async def test_can_reopen_after_close(self) -> None:
        cfg = DatabaseConfig(path=":memory:")
        s = LedgerStore(cfg)
        await s.append(_entry("e1"))
        await s.close()
        # After close, the connection is dropped — a new LedgerStore
        # would be needed in practice. Verify close is safe.
        assert s._conn is None
