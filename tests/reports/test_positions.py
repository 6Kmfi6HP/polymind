"""Test position reporter."""
import pytest
from datetime import datetime
from polymind.core.ledger import LedgerEntry, EntryType
from polymind.storage.database import DatabaseConfig
from polymind.storage.ledger import LedgerStore
from polymind.execution.executor import PositionRecord


@pytest.mark.asyncio
async def test_get_position_report():
    store = LedgerStore(DatabaseConfig(path=":memory:"))
    await store.update_position("0xabc", PositionRecord(
        market_id="0xabc", outcome="YES", size=100.0, avg_entry=0.50, realized_pnl=5.0
    ))
    from polymind.reports.positions import get_position_report
    positions = await get_position_report(store)
    assert len(positions) == 1
    assert positions[0].market_id == "0xabc"


@pytest.mark.asyncio
async def test_get_position_report_empty():
    store = LedgerStore(DatabaseConfig(path=":memory:"))
    from polymind.reports.positions import get_position_report
    positions = await get_position_report(store)
    assert len(positions) == 0


def test_format_positions_table():
    from polymind.reports.positions import format_positions_table
    from polymind.execution.executor import PositionRecord
    positions = [
        PositionRecord(market_id="0xabc", outcome="YES", size=100.0, avg_entry=0.50, realized_pnl=5.0)
    ]
    table = format_positions_table(positions)
    from rich.table import Table
    assert isinstance(table, Table)
    assert table.row_count == 1
