"""
Factor strategy backtesting.

A lightweight, synchronous backtester that evaluates factor scores against
market snapshots.  The ``FactorBacktester`` maintains internal position state
across ``run()`` calls so that multi-period simulations can track entry prices,
closed P&L, and performance metrics such as Sharpe, Sortino, and max drawdown.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from polymind.execution.fill_model import MarketSnapshot


@dataclass
class FactorBacktestResult:
    """Result of a single ``FactorBacktester.run()`` step.

    Attributes:
        market_id: Comma-joined IDs of the markets that were traded.
        total_trades: Number of positions opened or closed during this step.
        win_rate: Fraction of closed trades that were profitable (0.0-1.0).
        sharpe: Annualised Sharpe ratio computed over the PnL history so far.
        sortino: Annualised Sortino ratio computed over the PnL history so far.
        max_drawdown: Maximum peak-to-trough decline in cumulative PnL.
        total_return: Sum of realised PnL from closed positions.
        pnl_history: Chronological list of per-step realised PnL values.
    """

    market_id: str = ""
    total_trades: int = 0
    win_rate: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    max_drawdown: float = 0.0
    total_return: float = 0.0
    pnl_history: list[float] = field(default_factory=list)

    @property
    def num_winners(self) -> int:
        """Number of profitable trades derived from win_rate and total_trades."""
        return round(self.win_rate * self.total_trades)

    @property
    def num_losers(self) -> int:
        """Number of unprofitable trades."""
        return self.total_trades - self.num_winners


@dataclass
class FactorBacktestConfig:
    """Configuration for the factor backtester.

    Attributes:
        initial_capital: Starting cash balance for position sizing.
        lookback_days: Number of historical days used for factor computation.
        rebal_freq_hours: Hours between rebalance events.
        top_n: Number of highest-scoring markets to hold positions in.
        max_position_size: Maximum capital allocated to a single position.
    """

    initial_capital: float = 10000.0
    lookback_days: int = 30
    rebal_freq_hours: int = 4
    top_n: int = 5
    max_position_size: float = 1000.0


class FactorBacktester:
    """Lightweight synchronous backtester for factor-based strategies.

    Maintains internal position state (entry price per market) across
    successive ``run()`` calls so that the caller can iterate over
    historical time steps.

    Usage::

        config = FactorBacktestConfig(top_n=3, max_position_size=500.0)
        bt = FactorBacktester(config)

        for scores, snapshots in historical_data:
            result = bt.run(scores, snapshots)
            # inspect result.pnl_history, result.sharpe, etc.
    """

    def __init__(self, config: FactorBacktestConfig) -> None:
        self.config = config
        self._positions: dict[str, float] = {}
        self._pnl_history: list[float] = []
        self._cumulative_pnl: float = 0.0
        self._peak_cumulative: float = 0.0
        self._total_trades: int = 0
        self._winners: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        scores: dict[str, float],
        snapshots: dict[str, MarketSnapshot],
    ) -> FactorBacktestResult:
        """Run one backtest step.

        Selects the ``top_n`` markets by score, opens positions in new
        entrants, closes positions in dropped markets, and computes
        performance metrics based on the accumulated state.

        Args:
            scores: Map of ``market_id`` to numeric factor score (higher
                is better).
            snapshots: Map of ``market_id`` to current :class:`MarketSnapshot`
                containing at least a ``mid_price``.

        Returns:
            A :class:`FactorBacktestResult` summarising this step.
        """
        if not scores or not snapshots:
            # Close remaining open positions when no new scores arrive
            step_pnl = 0.0
            step_trades = 0
            for market_id in list(self._positions.keys()):
                snap = snapshots.get(market_id)
                if snap is not None:
                    step_trades += 1
                    step_pnl += self._close_position(market_id, snap.bid_price)

            if step_trades > 0:
                self._pnl_history.append(step_pnl)
                self._cumulative_pnl += step_pnl
                if self._cumulative_pnl > self._peak_cumulative:
                    self._peak_cumulative = self._cumulative_pnl
                self._total_trades += step_trades

            return self._build_result()

        # --- 1. Select top-N markets by score ---------------------------
        sorted_mkts = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        selected: set[str] = {m[0] for m in sorted_mkts[: self.config.top_n]}

        step_pnl = 0.0
        step_trades = 0

        # --- 2. Close positions that fell out of the top-N ---------------
        for market_id in list(self._positions.keys()):
            if market_id not in selected:
                snap = snapshots.get(market_id)
                if snap is not None:
                    step_trades += 1
                    step_pnl += self._close_position(market_id, snap.bid_price)

        # --- 3. Open new positions in entrants ---------------------------
        for market_id in selected:
            snap = snapshots.get(market_id)
            if snap is None:
                continue
            if market_id not in self._positions:
                step_trades += 1
                # Buy at ask (pay spread to enter)
                self._open_position(market_id, snap.ask_price)

        # --- 4. Update aggregate state -----------------------------------
        if step_trades > 0:
            self._pnl_history.append(step_pnl)
            self._cumulative_pnl += step_pnl
            if self._cumulative_pnl > self._peak_cumulative:
                self._peak_cumulative = self._cumulative_pnl
            self._total_trades += step_trades

        return self._build_result(
            market_id=", ".join(sorted(selected)),
            step_trades=step_trades,
            step_pnl=step_pnl,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _close_position(self, market_id: str, exit_price: float) -> float:
        """Close a tracked position and return the realised P&L."""
        entry = self._positions.pop(market_id, exit_price)
        pnl = exit_price - entry
        if pnl > 0:
            self._winners += 1
        return pnl

    def _open_position(self, market_id: str, entry_price: float) -> None:
        """Record a new position at *entry_price*."""
        self._positions[market_id] = entry_price

    def _build_result(
        self,
        market_id: str = "",
        step_trades: int = 0,
        step_pnl: float = 0.0,
    ) -> FactorBacktestResult:
        """Assemble a :class:`FactorBacktestResult` from current state."""
        pnl_hist = list(self._pnl_history)
        total_trades = self._total_trades
        winners = self._winners

        sharpe = 0.0
        sortino = 0.0
        max_dd = 0.0

        if len(pnl_hist) > 1:
            sharpe = _compute_sharpe(pnl_hist)
            sortino = _compute_sortino(pnl_hist)
            max_dd = _compute_max_drawdown(pnl_hist)

        return FactorBacktestResult(
            market_id=market_id,
            total_trades=total_trades,
            win_rate=winners / total_trades if total_trades > 0 else 0.0,
            sharpe=sharpe,
            sortino=sortino,
            max_drawdown=max_dd,
            total_return=self._cumulative_pnl,
            pnl_history=pnl_hist,
        )


# ======================================================================
# Standalone metric helpers
# ======================================================================


def _compute_sharpe(pnl_history: list[float], periods_per_year: int = 252) -> float:
    """Annualised Sharpe ratio from a PnL series."""
    if len(pnl_history) < 2:
        return 0.0
    mean_ = sum(pnl_history) / len(pnl_history)
    var_ = sum((x - mean_) ** 2 for x in pnl_history) / len(pnl_history)
    std_ = var_**0.5
    if std_ == 0.0:
        return 0.0
    return (mean_ / std_) * (periods_per_year**0.5)


def _compute_sortino(pnl_history: list[float], periods_per_year: int = 252) -> float:
    """Annualised Sortino ratio from a PnL series (downside deviation only)."""
    if len(pnl_history) < 2:
        return 0.0
    mean_ = sum(pnl_history) / len(pnl_history)
    downside = [x for x in pnl_history if x < 0]
    if not downside:
        return 0.0
    down_var = sum(x * x for x in downside) / len(pnl_history)
    down_std = down_var**0.5
    if down_std == 0.0:
        return 0.0
    return (mean_ / down_std) * (periods_per_year**0.5)


def _compute_max_drawdown(pnl_history: list[float]) -> float:
    """Maximum peak-to-trough drawdown of a cumulative PnL series."""
    peak = 0.0
    cumulative = 0.0
    max_dd = 0.0
    for x in pnl_history:
        cumulative += x
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    return max_dd
