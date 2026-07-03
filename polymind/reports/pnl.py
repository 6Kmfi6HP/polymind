"""P&L summary report."""

from __future__ import annotations

from rich.table import Table

from polymind.storage.ledger import LedgerStore


async def get_pnl_report(ledger: LedgerStore) -> list[dict]:
    """Fetch per-market P&L from the ledger store."""
    conn = await ledger._ensure_connection()
    assert ledger._conn is not None
    rows = await ledger._conn.fetch_all(
        "SELECT market_id, COALESCE(SUM(delta_cash), 0.0) AS realized_pnl "
        "FROM ledger_entries GROUP BY market_id ORDER BY realized_pnl DESC"
    )
    return [
        {"market_id": row["market_id"], "realized_pnl": row["realized_pnl"]}
        for row in rows
    ]


def format_pnl_table(report: list[dict], total_cash: float) -> Table:
    """Format P&L data as a Rich table."""
    table = Table(title="Profit & Loss Summary", show_header=True, header_style="bold")
    table.add_column("Market", style="cyan", no_wrap=True)
    table.add_column("Realized P&L", justify="right")

    total_pnl = 0.0
    for r in report:
        pnl = r["realized_pnl"]
        total_pnl += pnl
        pnl_str = f"[green]+${pnl:.2f}[/green]" if pnl >= 0 else f"[red]-${abs(pnl):.2f}[/red]"
        table.add_row(r["market_id"][:10] + "...", pnl_str)

    table.add_section()
    total_str = f"[green]+${total_pnl:.2f}[/green]" if total_pnl >= 0 else f"[red]-${abs(total_pnl):.2f}[/red]"
    table.add_row("[bold]Total P&L[/bold]", total_str)
    table.add_row("[bold]Cash Balance[/bold]", f"${total_cash:.2f}")

    return table
