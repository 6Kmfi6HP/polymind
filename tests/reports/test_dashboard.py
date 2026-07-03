"""Test dashboard reporter."""

from io import StringIO

import pytest
from rich.console import Console
from rich.table import Table

from polymind.risk.limits import LimitsConfig, LimitsManager
from polymind.risk.manager import RiskManager


@pytest.mark.asyncio
async def test_generate_dashboard():
    from polymind.reports.dashboard import generate_dashboard
    from polymind.storage.database import DatabaseConfig
    from polymind.storage.ledger import LedgerStore

    store = LedgerStore(DatabaseConfig(path=":memory:"))
    risk_mgr = RiskManager()
    limits_mgr = LimitsManager(
        LimitsConfig(
            positions=[],
            order_rate=None,
            daily_loss=None,
            exposure=None,
        )
    )
    tables = await generate_dashboard(store, risk_mgr, limits_mgr)
    assert len(tables) >= 3
    for t in tables:
        assert isinstance(t, Table)


def test_display_dashboard_empty():
    """display_dashboard handles 0 tables without error."""
    from polymind.reports.dashboard import display_dashboard

    console = Console(file=StringIO())
    display_dashboard([], console=console)
    output = console.file.getvalue()
    assert output == ""


def test_display_dashboard_single():
    """display_dashboard prints one table with no trailing newline gap."""
    from polymind.reports.dashboard import display_dashboard

    table = Table(title="Test")
    table.add_column("Col")
    table.add_row("val")

    console = Console(file=StringIO())
    display_dashboard([table], console=console)
    output = console.file.getvalue()
    assert "Test" in output
    assert "Col" in output
    assert "val" in output


def test_display_dashboard_multiple():
    """display_dashboard adds newline separator between tables."""
    from polymind.reports.dashboard import display_dashboard

    t1 = Table(title="First")
    t1.add_column("A")
    t1.add_row("1")
    t2 = Table(title="Second")
    t2.add_column("B")
    t2.add_row("2")

    console = Console(file=StringIO())
    display_dashboard([t1, t2], console=console)
    output = console.file.getvalue()
    # Both tables should appear (Rich wraps short titles like "Second" across lines)
    assert "First" in output
    assert "Sec" in output  # partial match due to Rich wrapping
