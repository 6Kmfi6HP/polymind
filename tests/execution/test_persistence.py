"""
Tests for LedgerStore SQLite persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import OrderSide
from polymind.core.ledger import EntryType, LedgerEntry
from polymind.execution.persistence import LedgerStore


@pytest.fixture
def store() -> LedgerStore:
    return LedgerStore(":memory:")


@pytest.fixture
def sample_fill() -> FillEvent:
    return FillEvent(
        fill_id="fill-000001",
        market_id="0xabc",
        outcome="YES",
        side=OrderSide.BUY,
        price=0.85,
        size=10.0,
        fee=0.0255,
        timestamp=datetime.now(timezone.utc),
        source=FillSource.SIMULATED,
    )


@pytest.fixture
def sample_ledger() -> LedgerEntry:
    return LedgerEntry(
        entry_id="ledger-000001",
        entry_type=EntryType.FILL,
        timestamp=datetime.now(timezone.utc),
        market_id="0xabc",
        description="BUY 10 @ 0.85",
        delta_cash=-8.5255,
        delta_position=10.0,
        position_after=10.0,
        cash_after=991.4745,
        fill_ref="fill-000001",
    )


class TestLedgerStore:
    @pytest.mark.asyncio
    async def test_open_and_close(self, store: LedgerStore):
        await store.open()
        assert store._conn is not None
        await store.close()
        assert store._conn is None

    @pytest.mark.asyncio
    async def test_append_and_load_fill(
        self, store: LedgerStore, sample_fill: FillEvent
    ):
        await store.open()
        await store.append_fill(sample_fill)
        fills = await store.load_fills()
        assert len(fills) == 1
        assert fills[0].fill_id == sample_fill.fill_id
        assert fills[0].market_id == sample_fill.market_id
        assert fills[0].price == sample_fill.price
        assert fills[0].side == sample_fill.side
        await store.close()

    @pytest.mark.asyncio
    async def test_append_and_load_ledger(
        self, store: LedgerStore, sample_ledger: LedgerEntry
    ):
        await store.open()
        await store.append_ledger(sample_ledger)
        entries = await store.load_ledger()
        assert len(entries) == 1
        assert entries[0].entry_id == sample_ledger.entry_id
        assert entries[0].entry_type == sample_ledger.entry_type
        assert entries[0].delta_cash == sample_ledger.delta_cash
        await store.close()

    @pytest.mark.asyncio
    async def test_append_duplicate_fill(
        self, store: LedgerStore, sample_fill: FillEvent
    ):
        """Duplicate fill_id should be ignored (INSERT OR IGNORE)."""
        await store.open()
        await store.append_fill(sample_fill)
        await store.append_fill(sample_fill)  # same fill_id
        fills = await store.load_fills()
        assert len(fills) == 1  # deduped
        await store.close()

    @pytest.mark.asyncio
    async def test_clear(self, store: LedgerStore, sample_fill: FillEvent, sample_ledger: LedgerEntry):
        await store.open()
        await store.append_fill(sample_fill)
        await store.append_ledger(sample_ledger)
        await store.clear()
        assert await store.get_fill_count() == 0
        assert await store.get_ledger_count() == 0
        await store.close()

    @pytest.mark.asyncio
    async def test_empty_store_counts(self, store: LedgerStore):
        await store.open()
        assert await store.get_fill_count() == 0
        assert await store.get_ledger_count() == 0
        await store.close()

    @pytest.mark.asyncio
    async def test_multiple_fills(self, store: LedgerStore, sample_fill: FillEvent):
        await store.open()
        await store.append_fill(sample_fill)

        fill2 = FillEvent(
            fill_id="fill-000002",
            market_id="0xdef",
            outcome="NO",
            side=OrderSide.SELL,
            price=0.12,
            size=5.0,
            fee=0.003,
            timestamp=datetime.now(timezone.utc),
            source=FillSource.SIMULATED,
        )
        await store.append_fill(fill2)
        fills = await store.load_fills()
        assert len(fills) == 2
        await store.close()

    @pytest.mark.asyncio
    async def test_fill_with_order_id(self, store: LedgerStore):
        await store.open()
        fill = FillEvent(
            fill_id="fill-000003",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.75,
            size=20.0,
            fee=0.045,
            timestamp=datetime.now(timezone.utc),
            source=FillSource.WEBSOCKET,
            order_id="ord-123",
            taker=False,
            metadata={"strategy": "amm_test"},
        )
        await store.append_fill(fill)
        fills = await store.load_fills()
        assert fills[0].order_id == "ord-123"
        assert fills[0].taker is False
        assert fills[0].metadata["strategy"] == "amm_test"
        await store.close()

    @pytest.mark.asyncio
    async def test_not_opened_error(self, store: LedgerStore):
        """Operations before open() should raise RuntimeError."""
        with pytest.raises(RuntimeError, match="Store not opened"):
            await store.append_fill(
                FillEvent(
                    fill_id="x",
                    market_id="x",
                    outcome="YES",
                    side=OrderSide.BUY,
                    price=0.5,
                    size=10.0,
                    fee=0.0,
                    timestamp=datetime.now(timezone.utc),
                    source=FillSource.SIMULATED,
                )
            )
