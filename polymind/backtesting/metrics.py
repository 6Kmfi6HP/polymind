"""
Performance metrics for backtesting and live trading.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""

    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    annualized_volatility_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    num_trades: int = 0
    avg_trade_pnl: float = 0.0


def compute_metrics(
    returns: list[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> PerformanceMetrics:
    """Compute performance metrics from a return series.

    Args:
        returns: List of periodic returns (decimal, e.g. 0.01 = 1%).
        risk_free_rate: Annual risk-free rate.
        periods_per_year: Number of periods per year (252 for daily).

    Returns:
        PerformanceMetrics object.
    """
    m = PerformanceMetrics()

    if not returns:
        return m

    m.num_trades = len(returns)
    m.total_return_pct = (sum(returns) / len(returns)) * 100

    winners = [r for r in returns if r > 0]
    losers = [r for r in returns if r < 0]
    m.win_rate = len(winners) / len(returns) if returns else 0.0
    m.profit_factor = (
        abs(sum(winners) / sum(losers)) if losers and sum(losers) != 0 else float("inf")
    )

    avg_return = sum(returns) / len(returns)
    variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)

    m.annualized_return_pct = avg_return * periods_per_year * 100
    m.annualized_volatility_pct = std_dev * math.sqrt(periods_per_year) * 100

    if std_dev > 0:
        excess_return = avg_return - (risk_free_rate / periods_per_year)
        m.sharpe_ratio = (excess_return / std_dev) * math.sqrt(periods_per_year)

        downside = [r for r in returns if r < 0]
        if downside:
            downside_var = sum((r - 0) ** 2 for r in downside) / len(returns)
            downside_std = math.sqrt(downside_var)
            m.sortino_ratio = (
                (avg_return * periods_per_year - risk_free_rate)
                / (downside_std * math.sqrt(periods_per_year))
                if downside_std > 0
                else 0.0
            )

    # Max drawdown
    peak = 0.0
    cumulative = 0.0
    for r in returns:
        cumulative += r
        if cumulative > peak:
            peak = cumulative
        drawdown = (peak - cumulative) / (1 + peak) if peak > 0 else 0.0
        m.max_drawdown_pct = max(m.max_drawdown_pct, drawdown * 100)

    m.calmar_ratio = (
        m.annualized_return_pct / m.max_drawdown_pct
        if m.max_drawdown_pct > 0
        else 0.0
    )

    m.avg_trade_pnl = sum(returns) / len(returns) * 100

    return m
