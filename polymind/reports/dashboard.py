"""Combined operator dashboard."""
from __future__ import annotations

from rich.console import Console
from rich.table import Table

from polymind.risk.limits import LimitsManager
from polymind.risk.manager import RiskManager
from polymind.storage.ledger import LedgerStore

from .positions import format_positions_table, get_position_report
from .pnl import format_pnl_table, get_pnl_report
from .risk import format_risk_table, get_risk_report


async def generate_dashboard(
    ledger: LedgerStore,
    risk_mgr: RiskManager,
    limits_mgr: LimitsManager,
) -> list[Table]:
    """Generate all dashboard tables."""
    positions = await get_position_report(ledger)
    pnl_data = await get_pnl_report(ledger)
    cash = await ledger.get_cash_balance()
    risk = get_risk_report(risk_mgr, limits_mgr)

    return [
        format_positions_table(positions),
        format_pnl_table(pnl_data, cash),
        format_risk_table(risk),
    ]


def display_dashboard(tables: list[Table], console: Console | None = None) -> None:
    """Print all dashboard tables to console."""
    console = console or Console()
    for i, table in enumerate(tables):
        console.print(table)
        if i < len(tables) - 1:
            console.print()
