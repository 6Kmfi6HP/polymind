"""Test dashboard reporter."""

import pytest

from polymind.risk.manager import RiskManager
from polymind.risk.limits import LimitsConfig, LimitsManager


@pytest.mark.asyncio
async def test_generate_dashboard():
    from polymind.storage.database import DatabaseConfig
    from polymind.storage.ledger import LedgerStore
    from polymind.reports.dashboard import generate_dashboard
    from rich.table import Table

    store = LedgerStore(DatabaseConfig(path=":memory:"))
    risk_mgr = RiskManager()
    limits_mgr = LimitsManager(LimitsConfig(
        positions=[], order_rate=None, daily_loss=None, exposure=None,
    ))
    tables = await generate_dashboard(store, risk_mgr, limits_mgr)
    assert len(tables) >= 3
    for t in tables:
        assert isinstance(t, Table)
