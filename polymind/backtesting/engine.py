"""
Portfolio backtesting engine for factor strategies.

Simulates trading on historical snapshots using the factor pipeline.
Records P&L, Sharpe ratio, and position-level attribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from polymind.core.portfolio import PortfolioTarget
from polymind.factors.pipeline import FactorPipeline, UniverseSnapshot


@dataclass
class BacktestResult:
    """Result of a backtest run."""

    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0
    num_winners: int = 0
    num_losers: int = 0
    pnl_series: list[float] = field(default_factory=list)
    portfolio_values: list[float] = field(default_factory=list)
    timestamps: list[datetime] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)


@dataclass
class BacktestConfig:
    """Configuration for backtesting."""

    initial_capital: float = 10_000.0
    commission_pct: float = 0.001  # 0.1% per trade


class BacktestEngine:
    """Simple portfolio backtesting engine.

    Walks through historical snapshots, runs the factor pipeline on each,
    executes trades, and records performance metrics.
    """

    def __init__(
        self,
        pipeline: FactorPipeline,
        config: BacktestConfig | None = None,
    ):
        self.pipeline = pipeline
        self.config = config or BacktestConfig()

    async def run(
        self,
        snapshots: list[UniverseSnapshot],
    ) -> BacktestResult:
        """Run a backtest over a sequence of historical snapshots.

        Args:
            snapshots: Chronological list of universe snapshots.

        Returns:
            BacktestResult with performance metrics.
        """
        capital = self.config.initial_capital
        positions: dict[str, float] = {}
        entry_prices: dict[str, float] = {}

        result = BacktestResult()
        result.portfolio_values.append(capital)
        pnl = 0.0

        for snap in snapshots:
            targets = await self.pipeline.run(snap)
            pnl = self._process_targets(snap, targets, positions, entry_prices, capital, result)
            capital += pnl
            result.portfolio_values.append(capital)

        # Final metrics
        result.total_return_pct = (
            (capital - self.config.initial_capital) / self.config.initial_capital * 100
        )
        if result.pnl_series:
            mean_pnl = sum(result.pnl_series) / len(result.pnl_series)
            var_pnl = sum((x - mean_pnl) ** 2 for x in result.pnl_series) / len(result.pnl_series)
            std_pnl = var_pnl**0.5
            result.sharpe_ratio = (mean_pnl / std_pnl) * (252**0.5) if std_pnl > 0 else 0.0

        return result

    def _process_targets(
        self,
        snap: UniverseSnapshot,
        targets: list[PortfolioTarget],
        positions: dict[str, float],
        entry_prices: dict[str, float],
        capital: float,
        result: BacktestResult,
    ) -> float:
        """Process pipeline targets and execute trades.

        Returns P&L for this tick.
        """
        total_pnl = 0.0
        target_mids = {t.market_id for t in targets}

        # Close positions not in targets
        for mid in list(positions.keys()):
            if mid not in target_mids and positions[mid] != 0:
                total_pnl += self._close_position(mid, snap, positions, entry_prices, result)
                result.trades.append(
                    {
                        "market_id": mid,
                        "action": "close",
                        "timestamp": snap.timestamp.isoformat(),
                    }
                )

        # Open / adjust target positions
        for t in targets:
            size_delta = t.target_size - positions.get(t.market_id, 0.0)
            if abs(size_delta) > 0:
                price = self._execution_price(t, snap)
                cost = abs(size_delta) * price * self.config.commission_pct
                total_pnl -= cost
                positions[t.market_id] = t.target_size
                entry_prices[t.market_id] = price
                result.trades.append(
                    {
                        "market_id": t.market_id,
                        "action": "open" if positions.get(t.market_id, 0.0) == 0 else "adjust",
                        "direction": t.direction.name,
                        "size": t.target_size,
                        "price": price,
                        "timestamp": snap.timestamp.isoformat(),
                    }
                )

        result.pnl_series.append(total_pnl)
        return total_pnl

    @staticmethod
    def _close_position(
        mid: str,
        snap: UniverseSnapshot,
        positions: dict[str, float],
        entry_prices: dict[str, float],
        result: BacktestResult,
    ) -> float:
        """Close a position and record P&L."""
        mf = snap.markets.get(mid)
        if mf is None:
            positions.pop(mid, None)
            return 0.0

        close_price = mf.mid_price
        entry = entry_prices.pop(mid, close_price)
        size = positions.pop(mid, 0.0)
        pnl = size * (close_price - entry)
        if pnl > 0:
            result.num_winners += 1
        elif pnl < 0:
            result.num_losers += 1
        result.num_trades += 1
        return pnl

    @staticmethod
    def _execution_price(target: PortfolioTarget, snap: UniverseSnapshot) -> float:
        """Determine execution price for a target."""
        mf = snap.markets.get(target.market_id)
        if mf is None:
            return 0.5
        return mf.mid_price
