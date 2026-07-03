"""Position summary report."""

from __future__ import annotations

from rich.table import Table

from polymind.execution.executor import PositionRecord
from polymind.storage.ledger import LedgerStore


async def get_position_report(ledger: LedgerStore) -> list[PositionRecord]:
    """Fetch all positions from the ledger store."""
    conn = await ledger._ensure_connection()
    assert ledger._conn is not None
    rows = await ledger._conn.fetch_all(
        "SELECT * FROM positions ORDER BY market_id"
    )
    return [
        PositionRecord(
            market_id=row["market_id"],
            outcome=row["outcome"],
            size=row["size"],
            avg_entry=row["avg_entry"],
            realized_pnl=row["realized_pnl"],
        )
        for row in rows
    ]


def format_positions_table(positions: list[PositionRecord]) -> Table:
    """Format positions as a Rich table."""
    table = Table(title="Open Positions", show_header=True, header_style="bold")
    table.add_column("Market", style="cyan", no_wrap=True)
    table.add_column("Outcome")
    table.add_column("Size", justify="right")
    table.add_column("Avg Entry", justify="right")
    table.add_column("Realized P&L", justify="right")

    for p in positions:
        pnl_str = (
            f"[green]+${p.realized_pnl:.2f}[/green]"
            if p.realized_pnl >= 0
            else f"[red]-${abs(p.realized_pnl):.2f}[/red]"
        )
        table.add_row(
            p.market_id[:10] + "...",
            p.outcome or "N/A",
            str(p.size),
            f"${p.avg_entry:.4f}",
            pnl_str,
        )

    return table
