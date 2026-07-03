"""Test dashboard reporter."""
import pytest
from polymind.storage.database import DatabaseConfig
from polymind.storage.ledger import LedgerStore
from polymind.risk.manager import RiskManager
from polymind.risk.limits import LimitsConfig, LimitsManager


@pytest.mark.asyncio
async def test_generate_dashboard():
    store = LedgerStore(DatabaseConfig(path=":memory:"))
    risk_mgr = RiskManager()
    limits_mgr = LimitsManager(LimitsConfig(
        positions=[], order_rate=None, daily_loss=None, exposure=None,
    ))
    from polymind.reports.dashboard import generate_dashboard
    tables = await generate_dashboard(store, risk_mgr, limits_mgr)
    assert len(tables) >= 3  # positions, pnl, risk
    for t in tables:
        from rich.table import Table
        assert isinstance(t, Table)
