"""Test position reporter."""

import pytest

from polymind.execution.executor import PositionRecord


@pytest.mark.asyncio
async def test_get_position_report():
    from polymind.reports.positions import get_position_report
    from polymind.storage.database import DatabaseConfig
    from polymind.storage.ledger import LedgerStore

    store = LedgerStore(DatabaseConfig(path=":memory:"))
    await store.update_position(
        "0xabc",
        PositionRecord(
            market_id="0xabc", outcome="YES", size=100.0, avg_entry=0.50, realized_pnl=5.0
        ),
    )
    positions = await get_position_report(store)
    assert len(positions) == 1
    assert positions[0].market_id == "0xabc"


@pytest.mark.asyncio
async def test_get_position_report_empty():
    from polymind.reports.positions import get_position_report
    from polymind.storage.database import DatabaseConfig
    from polymind.storage.ledger import LedgerStore

    store = LedgerStore(DatabaseConfig(path=":memory:"))
    positions = await get_position_report(store)
    assert len(positions) == 0


def test_format_positions_table():
    from rich.table import Table

    from polymind.reports.positions import format_positions_table

    positions = [
        PositionRecord(
            market_id="0xabc", outcome="YES", size=100.0, avg_entry=0.50, realized_pnl=5.0
        )
    ]
    table = format_positions_table(positions)
    assert isinstance(table, Table)
