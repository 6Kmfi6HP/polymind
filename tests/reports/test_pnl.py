"""Test P&L reporter."""

from datetime import datetime

import pytest

from polymind.core.ledger import EntryType, LedgerEntry


@pytest.mark.asyncio
async def test_get_pnl_report():
    from polymind.reports.pnl import get_pnl_report
    from polymind.storage.database import DatabaseConfig
    from polymind.storage.ledger import LedgerStore

    store = LedgerStore(DatabaseConfig(path=":memory:"))
    await store.append(
        LedgerEntry(
            entry_id="e1",
            entry_type=EntryType.FILL,
            timestamp=datetime(2026, 1, 1),
            market_id="0xabc",
            description="Buy",
            delta_cash=-50.0,
            delta_position=100.0,
            position_after=100.0,
            cash_after=950.0,
        )
    )
    report = await get_pnl_report(store)
    assert len(report) == 1
    assert report[0]["market_id"] == "0xabc"


@pytest.mark.asyncio
async def test_get_pnl_report_empty():
    from polymind.reports.pnl import get_pnl_report
    from polymind.storage.database import DatabaseConfig
    from polymind.storage.ledger import LedgerStore

    store = LedgerStore(DatabaseConfig(path=":memory:"))
    report = await get_pnl_report(store)
    assert len(report) == 0


def test_format_pnl_table():
    from rich.table import Table

    from polymind.reports.pnl import format_pnl_table

    report = [{"market_id": "0xabc", "realized_pnl": 5.0}]
    table = format_pnl_table(report, total_cash=1000.0)
    assert isinstance(table, Table)
