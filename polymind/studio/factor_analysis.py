"""
Advanced factor analysis — IC, decay, walk-forward, and statistical measures.

Extends the FactorBacktester with Information Coefficient analysis,
factor half-life decay estimation, and walk-forward cross-validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from polymind.backtesting.factor_bt import (
    FactorBacktestConfig,
    FactorBacktester,
)
from polymind.execution.fill_model import MarketSnapshot


@dataclass
class ICAnalysis:
    """Information Coefficient analysis for a factor.

    Parameters
    ----------
    ic_values:
        IC values per time period.
    ic_mean:
        Mean IC across all periods.
    ic_std:
        Standard deviation of IC.
    ic_ir:
        Information Coefficient IR (mean / std), annualized.
    rank_ic:
        Spearman rank correlation across all periods combined.
    decile_returns:
        Average forward return per decile (decile_1 = highest scores).
    hit_rate:
        Fraction of periods where IC > 0.
    """

    ic_values: list[float] = field(default_factory=list)
    ic_mean: float = 0.0
    ic_std: float = 0.0
    ic_ir: float = 0.0
    rank_ic: float = 0.0
    decile_returns: list[float] = field(default_factory=list)
    hit_rate: float = 0.0


@dataclass
class WalkForwardResult:
    """Result of walk-forward factor analysis.

    Parameters
    ----------
    period_results:
        FactorCard-like results per period.
    sharpe_mean:
        Mean Sharpe across periods.
    sharpe_std:
        Standard deviation of Sharpe across periods.
    sharpe_consistency:
        Fraction of periods with Sharpe > 0.
    avg_drawdown:
        Average max drawdown across periods.
    """

    period_results: list[dict[str, Any]] = field(default_factory=list)
    sharpe_mean: float = 0.0
    sharpe_std: float = 0.0
    sharpe_consistency: float = 0.0
    avg_drawdown: float = 0.0


# ======================================================================
# FactorAnalyzer
# ======================================================================


class FactorAnalyzer:
    """Advanced factor analysis toolkit.

    Provides Information Coefficient (IC) calculation, factor decay
    estimation, and walk-forward cross-validation.
    """

    @staticmethod
    def compute_ic(
        scores: dict[str, float],
        forward_returns: dict[str, float],
    ) -> ICAnalysis:
        """Compute IC analysis from a set of scores vs forward returns.

        Parameters
        ----------
        scores:
            Market ID → factor score.
        forward_returns:
            Market ID → forward return (e.g. mid_price change over N periods).

        Returns
        -------
        ICAnalysis
            IC statistics and decile breakdown.
        """
        common = [m for m in scores if m in forward_returns]
        if len(common) < 3:
            return ICAnalysis()

        # Spearman rank correlation
        ranked_scores = sorted((scores[m], m) for m in common)
        ranked_returns = sorted((forward_returns[m], m) for m in common)

        score_ranks = {m: i for i, (_, m) in enumerate(ranked_scores)}
        return_ranks = {m: i for i, (_, m) in enumerate(ranked_returns)}

        n = len(common)
        d_sq = sum((score_ranks[m] - return_ranks[m]) ** 2 for m in common)
        rank_ic = 1.0 - (6.0 * d_sq) / (n * (n * n - 1)) if n > 1 else 0.0

        # Decile returns
        decile_size = max(1, n // 10)
        sorted_by_score = sorted((scores[m], m) for m in common)
        decile_returns: list[float] = []
        for d in range(10):
            start = d * decile_size
            end = start + decile_size if d < 9 else n
            decile = sorted_by_score[start:end]
            if decile:
                decile_returns.append(sum(forward_returns[m] for _, m in decile) / len(decile))

        # Single-period IC values (placeholder for multi-period analysis)
        ic_values = [rank_ic]
        ic_mean = rank_ic
        ic_std = 0.0
        ic_ir = 0.0
        hit_rate = 1.0 if rank_ic > 0 else 0.0

        return ICAnalysis(
            ic_values=ic_values,
            ic_mean=ic_mean,
            ic_std=ic_std,
            ic_ir=ic_ir,
            rank_ic=rank_ic,
            decile_returns=decile_returns,
            hit_rate=hit_rate,
        )

    @staticmethod
    def compute_ic_series(
        score_series: list[dict[str, float]],
        forward_return_series: list[dict[str, float]],
    ) -> ICAnalysis:
        """Compute IC over a time series of score/return pairs.

        Parameters
        ----------
        score_series:
            Factor scores per time period.
        forward_return_series:
            Forward returns per time period (same length as score_series).

        Returns
        -------
        ICAnalysis
            Full IC analysis with time-series statistics.
        """
        if not score_series or not forward_return_series:
            return ICAnalysis()
        if len(score_series) != len(forward_return_series):
            return ICAnalysis()

        all_ic_values: list[float] = []
        all_decile_returns: list[list[float]] = []

        for scores, returns in zip(score_series, forward_return_series, strict=False):
            common = [m for m in scores if m in returns]
            if len(common) < 3:
                continue

            n = len(common)
            ranked_scores = sorted((scores[m], m) for m in common)
            ranked_returns = sorted((returns[m], m) for m in common)

            score_ranks = {m: i for i, (_, m) in enumerate(ranked_scores)}
            return_ranks = {m: i for i, (_, m) in enumerate(ranked_returns)}

            d_sq = sum((score_ranks[m] - return_ranks[m]) ** 2 for m in common)
            ic = 1.0 - (6.0 * d_sq) / (n * (n * n - 1)) if n > 1 else 0.0
            all_ic_values.append(ic)

            # Decile returns
            decile_size = max(1, n // 10)
            sorted_by_score = sorted((scores[m], m) for m in common)
            for d in range(10):
                start = d * decile_size
                end = start + decile_size if d < 9 else n
                decile = sorted_by_score[start:end]
                if decile:
                    avg_ret = sum(returns[m] for _, m in decile) / len(decile)
                    if len(all_decile_returns) <= d:
                        all_decile_returns.append([avg_ret])
                    else:
                        all_decile_returns[d].append(avg_ret)

        if not all_ic_values:
            return ICAnalysis()

        ic_mean = sum(all_ic_values) / len(all_ic_values)
        ic_std = (sum((x - ic_mean) ** 2 for x in all_ic_values) / len(all_ic_values)) ** 0.5
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0
        hit_rate = sum(1 for v in all_ic_values if v > 0) / len(all_ic_values)

        # Average decile returns
        avg_decile: list[float] = []
        for dr in all_decile_returns:
            avg_decile.append(sum(dr) / len(dr))
        # Ensure 10 deciles
        while len(avg_decile) < 10:
            avg_decile.append(0.0)

        return ICAnalysis(
            ic_values=all_ic_values,
            ic_mean=ic_mean,
            ic_std=ic_std,
            ic_ir=ic_ir,
            rank_ic=all_ic_values[-1] if all_ic_values else 0.0,
            decile_returns=avg_decile,
            hit_rate=hit_rate,
        )

    @staticmethod
    def compute_decay(
        ic_series: list[float],
    ) -> float:
        """Estimate factor half-life in periods from IC decay.

        Uses exponential decay model: IC(t) ≈ IC(0) * exp(-λ * t).
        Half-life = ln(2) / λ.

        Parameters
        ----------
        ic_series:
            IC values over consecutive periods.

        Returns
        -------
        float
            Estimated half-life in periods. Returns 0 if insufficient data
            or no decay detected.
        """
        if len(ic_series) < 4:
            return 0.0

        # Simple approximation: compute auto-correlation at lag 1
        # Half-life ≈ -ln(2) / ln(|ρ|)
        lag_1 = FactorAnalyzer._autocorr(ic_series, 1)

        # Clamp to avoid exact ±1.0 (which would make log(|ρ|) → 0 or ∞)
        abs_rho = min(abs(lag_1), 0.9999)
        if abs_rho <= 0.0:
            return 0.0
        import math

        half_life = -math.log(2.0) / math.log(abs_rho)
        return max(0.0, half_life)

    @staticmethod
    def walk_forward(
        score_series: list[dict[str, float]],
        snapshot_series: list[dict[str, MarketSnapshot]],
        config: FactorBacktestConfig | None = None,
        window: int = 5,
        step: int = 1,
    ) -> WalkForwardResult:
        """Run walk-forward backtest on rolling windows.

        Parameters
        ----------
        score_series:
            Factor scores per time period.
        snapshot_series:
            Market snapshots per time period.
        config:
            Backtest configuration (uses defaults if None).
        window:
            Number of periods per window.
        step:
            Periods to slide between windows.

        Returns
        -------
        WalkForwardResult
            Aggregated walk-forward metrics.
        """
        cfg = config or FactorBacktestConfig()
        period_results: list[dict[str, Any]] = []

        if not score_series or not snapshot_series:
            return WalkForwardResult()

        if len(score_series) != len(snapshot_series):
            return WalkForwardResult()

        max_start = max(0, len(score_series) - window + 1)
        for w_start in range(0, max_start, step):
            bt = FactorBacktester(cfg)
            window_sharpes: list[float] = []
            window_dds: list[float] = []
            window_returns: list[float] = []
            total_trades = 0

            for i in range(w_start, min(w_start + window, len(score_series))):
                scores = score_series[i]
                snapshots = snapshot_series[i]
                result = bt.run(scores, snapshots)
                window_sharpes.append(result.sharpe)
                window_dds.append(result.max_drawdown)
                window_returns.append(result.total_return)
                total_trades += result.total_trades

            period_results.append(
                {
                    "window": w_start,
                    "sharpe": sum(window_sharpes) / len(window_sharpes) if window_sharpes else 0.0,
                    "max_drawdown": max(window_dds) if window_dds else 0.0,
                    "total_return": sum(window_returns) if window_returns else 0.0,
                    "total_trades": total_trades,
                }
            )

        if not period_results:
            return WalkForwardResult()

        sharpes = [r["sharpe"] for r in period_results]
        sharpe_mean = sum(sharpes) / len(sharpes)
        sharpe_std = (sum((s - sharpe_mean) ** 2 for s in sharpes) / len(sharpes)) ** 0.5
        sharpe_consistency = sum(1 for s in sharpes if s > 0) / len(sharpes)
        avg_dd = sum(r["max_drawdown"] for r in period_results) / len(period_results)

        return WalkForwardResult(
            period_results=period_results,
            sharpe_mean=sharpe_mean,
            sharpe_std=sharpe_std,
            sharpe_consistency=sharpe_consistency,
            avg_drawdown=avg_dd,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _autocorr(series: list[float], lag: int = 1) -> float:
        """Compute Pearson auto-correlation at a given lag."""
        if len(series) < lag + 2:
            return 0.0
        x = series[: len(series) - lag]
        y = series[lag:]
        n = len(x)
        mx = sum(x) / n
        my = sum(y) / n
        num = sum((x[i] - mx) * (y[i] - my) for i in range(n))
        den = (
            sum((x[i] - mx) ** 2 for i in range(n)) * sum((y[i] - my) ** 2 for i in range(n))
        ) ** 0.5
        if den == 0:
            return 0.0
        return num / den


__all__ = [
    "FactorAnalyzer",
    "ICAnalysis",
    "WalkForwardResult",
]
