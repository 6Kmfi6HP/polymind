"""Test risk reporter."""

from polymind.risk.limits import (
    DailyLossLimit,
    ExposureLimit,
    LimitsConfig,
    LimitsManager,
    OrderRateLimit,
    PositionLimit,
)
from polymind.risk.manager import RiskManager


def test_get_risk_report():
    from polymind.reports.risk import get_risk_report

    risk_mgr = RiskManager(initial_capital=1000.0)
    limits_mgr = LimitsManager(
        LimitsConfig(
            positions=[
                PositionLimit(market_id="0xabc", max_size=100.0, max_notional=500.0, min_size=1.0)
            ],
            order_rate=OrderRateLimit(max_orders_per_window=10, window_seconds=60),
            daily_loss=DailyLossLimit(max_loss_amount=100.0, max_loss_pct=0.10),
            exposure=ExposureLimit(max_total_exposure=5000.0, max_per_market_pct=0.30),
        )
    )
    report = get_risk_report(risk_mgr, limits_mgr)
    assert report.total_exposure == 0.0
    assert report.drawdown_pct == 0.0
    assert report.is_healthy


def test_get_risk_report_in_drawdown():
    from polymind.reports.risk import get_risk_report

    risk_mgr = RiskManager(initial_capital=1000.0)
    risk_mgr.current_capital = 850.0
    risk_mgr.peak_capital = 1000.0
    config = LimitsConfig(
        positions=[],
        order_rate=OrderRateLimit(max_orders_per_window=10, window_seconds=60),
        daily_loss=DailyLossLimit(max_loss_amount=100.0, max_loss_pct=0.10),
        exposure=ExposureLimit(max_total_exposure=5000.0, max_per_market_pct=0.30),
    )
    report = get_risk_report(risk_mgr, LimitsManager(config))
    assert report.drawdown_pct == 15.0
    assert not report.is_healthy


def test_format_risk_table():
    from rich.table import Table

    from polymind.reports.risk import RiskReport, format_risk_table

    report = RiskReport(
        total_exposure=100.0,
        max_exposure=5000.0,
        drawdown_pct=5.0,
        daily_loss=10.0,
        max_daily_loss=100.0,
        is_healthy=True,
    )
    table = format_risk_table(report)
    assert isinstance(table, Table)
