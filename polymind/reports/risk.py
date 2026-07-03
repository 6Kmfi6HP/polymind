"""Risk status report."""

from __future__ import annotations

from dataclasses import dataclass

from rich.table import Table

from polymind.risk.limits import LimitsManager
from polymind.risk.manager import RiskManager


@dataclass
class RiskReport:
    """Risk status summary."""
    total_exposure: float
    max_exposure: float
    drawdown_pct: float
    daily_loss: float
    max_daily_loss: float
    is_healthy: bool


def get_risk_report(risk_mgr: RiskManager, limits_mgr: LimitsManager) -> RiskReport:
    """Build a risk status report."""
    drawdown_pct = 0.0
    if risk_mgr.peak_capital > 0:
        drawdown_pct = (1 - risk_mgr.current_capital / risk_mgr.peak_capital) * 100

    return RiskReport(
        total_exposure=0.0,
        max_exposure=limits_mgr.config.exposure.max_total_exposure if limits_mgr.config.exposure else 5000.0,
        drawdown_pct=round(drawdown_pct, 2),
        daily_loss=risk_mgr._daily_loss,
        max_daily_loss=limits_mgr.config.daily_loss.max_loss_amount if limits_mgr.config.daily_loss else 100.0,
        is_healthy=drawdown_pct < 10.0,
    )


def format_risk_table(report: RiskReport) -> Table:
    """Format risk status as a Rich table."""
    table = Table(title="Risk Status", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_column("Status")

    health = "[green]HEALTHY[/green]" if report.is_healthy else "[red]ALERT[/red]"
    dd_color = "green" if report.drawdown_pct < 5 else "yellow" if report.drawdown_pct < 10 else "red"

    table.add_row("Drawdown", f"[{dd_color}]{report.drawdown_pct:.1f}%[/{dd_color}]", health)
    table.add_row("Total Exposure", f"${report.total_exposure:.2f}",
                  "[green]OK[/green]" if report.total_exposure < report.max_exposure else "[red]OVER[/red]")
    table.add_row("Daily Loss", f"${report.daily_loss:.2f}",
                  "[green]OK[/green]" if report.daily_loss < report.max_daily_loss else "[red]LIMIT HIT[/red]")
    table.add_row("System Health", "", health)

    return table
