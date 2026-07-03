"""Operator reports — positions, P&L, risk dashboard."""

from polymind.reports.dashboard import display_dashboard, generate_dashboard
from polymind.reports.pnl import format_pnl_table, get_pnl_report
from polymind.reports.positions import format_positions_table, get_position_report
from polymind.reports.risk import RiskReport, format_risk_table, get_risk_report

__version__ = "0.1.0"

__all__ = [
    "get_position_report",
    "format_positions_table",
    "get_pnl_report",
    "format_pnl_table",
    "get_risk_report",
    "format_risk_table",
    "RiskReport",
    "generate_dashboard",
    "display_dashboard",
]
