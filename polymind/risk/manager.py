"""
Risk management — position sizing, stop-loss, take-profit, and capital tracking.

Ported sizing methods from probablyprofit-ai-framework/risk/manager.py
(REF-001c).  Sub-modules (drawdown.py, limits.py, exposure.py) own
dedicated limit/state checks — this manager composes them and adds
position-sizing arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TradeRecord:
    """Record of a completed trade."""

    market_id: str
    side: str
    size: float
    price: float
    pnl: float = 0.0


class RiskManager:
    """Manages trading risk — exposure, sizing, and drawdown.

    Provides position-sizing methods (fixed_pct, confidence_based,
    kelly, dynamic) plus stop-loss / take-profit threshold checks.

    Ported from probablyprofit-ai-framework/risk/manager.py lines
    342–540 (REF-001c).  Anti-patterns rejected: Telegram alert
    coupling, global ``get_config()`` singletons, and persistence
    mixed into sizing logic.
    """

    def __init__(
        self,
        initial_capital: float = 1000.0,
        position_size_pct: float = 0.05,
        default_stop_loss_pct: float = 0.05,
        default_take_profit_pct: float = 0.15,
    ):
        if initial_capital <= 0:
            raise ValueError(f"initial_capital must be positive, got {initial_capital}")

        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_capital = initial_capital
        self.trades: list[TradeRecord | dict[str, Any]] = []

        # Configurable defaults
        self.position_size_pct = position_size_pct
        self.default_stop_loss_pct = default_stop_loss_pct
        self.default_take_profit_pct = default_take_profit_pct

        # Daily tracking
        self._daily_pnl = 0.0

    # ── Position sizing ────────────────────────────────────────────────────

    def calculate_position_size(
        self,
        price: float,
        confidence: float = 0.5,
        method: str = "fixed_pct",
        **kwargs: Any,
    ) -> float:
        """Calculate position size using the specified method.

        Parameters
        ----------
        price:
            Entry price (0–1 for binary markets).
        confidence:
            Confidence level (0–1).
        method:
            One of ``fixed_pct``, ``confidence_based``, ``kelly``,
            ``dynamic``, or ``manual`` (returns 0).
        **kwargs:
            Extra arguments forwarded to the chosen method:
            ``kelly_fraction`` (kelly), ``volatility``, ``win_streak``,
            ``lose_streak`` (dynamic).

        Returns
        -------
        float
            Position size in shares.
        """
        if method == "fixed_pct":
            position_value = self.current_capital * self.position_size_pct
            return position_value / price if price > 0 else 0.0

        if method == "confidence_based":
            adjusted_pct = self.position_size_pct * confidence
            position_value = self.current_capital * adjusted_pct
            return position_value / price if price > 0 else 0.0

        if method == "kelly":
            kelly_fraction = kwargs.get("kelly_fraction", 0.25)
            return self._kelly_size(confidence, price, fraction=kelly_fraction)

        if method == "dynamic":
            return self._dynamic_size(price, confidence, **kwargs)

        # manual or unknown method
        return 0.0

    def _kelly_size(
        self,
        win_prob: float,
        price: float,
        fraction: float = 0.25,
    ) -> float:
        """Kelly criterion position size.

        f* = win_prob - (1 - win_prob) / b
        where b = (1 - price) / price

        Parameters
        ----------
        win_prob:
            Estimated probability of winning (0–1).
        price:
            Entry price.
        fraction:
            Kelly fraction (e.g. 0.25 = Quarter Kelly).

        Returns
        -------
        float
            Position size in shares.
        """
        if price <= 0 or price >= 1:
            return 0.0
        net_odds = (1 - price) / price
        if net_odds == 0:
            return 0.0
        kelly_pct = win_prob - ((1 - win_prob) / net_odds)
        if kelly_pct <= 0:
            return 0.0
        position_value = self.current_capital * kelly_pct * fraction
        return position_value / price

    def _dynamic_size(
        self,
        price: float,
        confidence: float,
        volatility: float = 0.5,
        win_streak: int = 0,
        lose_streak: int = 0,
        **kwargs: Any,
    ) -> float:
        """Multi-factor dynamic position sizing.

        Combines confidence, volatility, streak, recent-performance,
        and capital-preservation into a single multiplier on the base
        ``position_size_pct``.  Ported from the reference's
        ``_dynamic_size`` method.

        Parameters
        ----------
        price:
            Entry price.
        confidence:
            Confidence (0–1).
        volatility:
            Market volatility (0–1, higher = more volatile).
        win_streak:
            Consecutive wins.
        lose_streak:
            Consecutive losses.

        Returns
        -------
        float
            Position size in shares.
        """
        # Confidence factor: 0.5× to 1.5×
        confidence_factor = 0.5 + confidence

        # Volatility factor: low vol → 1.2×, high vol → 0.6×
        volatility_factor = 1.4 - volatility

        # Streak factor
        if win_streak >= 3:
            streak_factor = min(1.3, 1.0 + win_streak * 0.05)
        elif lose_streak >= 2:
            streak_factor = max(0.5, 1.0 - lose_streak * 0.15)
        else:
            streak_factor = 1.0

        # Recent performance — reduce if currently losing
        perf_factor = 1.0
        if self._daily_pnl < 0:
            loss_ratio = abs(self._daily_pnl) / (self.current_capital + 1e-9)
            perf_factor = max(0.5, 1.0 - loss_ratio * 0.5)

        # Capital preservation — reduce if capital has shrunk
        capital_ratio = self.current_capital / self.initial_capital
        capital_factor = max(0.5, capital_ratio) if capital_ratio < 0.8 else 1.0

        combined_factor = (
            confidence_factor * volatility_factor * streak_factor * perf_factor * capital_factor
        )

        adjusted_pct = self.position_size_pct * combined_factor
        adjusted_pct = max(0.01, min(0.20, adjusted_pct))

        position_value = self.current_capital * adjusted_pct
        return position_value / price if price > 0 else 0.0

    # ── Position gates ─────────────────────────────────────────────────────

    def can_open_position(self, size: float, price: float) -> bool:
        """Check if a new position can be opened.

        Returns True if the position value does not exceed 10 % of
        current capital.
        """
        position_value = size * price
        return position_value <= self.current_capital * 0.1

    def should_stop_loss(
        self,
        entry_price: float,
        current_price: float,
        size: float,
        stop_loss_pct: float | None = None,
    ) -> bool:
        """Check if a stop-loss should be triggered.

        Parameters
        ----------
        entry_price:
            Original entry price.
        current_price:
            Current market price.
        size:
            Position size in shares.
        stop_loss_pct:
            Loss threshold (decimal).  Defaults to
            ``self.default_stop_loss_pct``.

        Returns
        -------
        bool
            True if the position should be stopped out.
        """
        pct = stop_loss_pct if stop_loss_pct is not None else self.default_stop_loss_pct
        entry_value = size * entry_price
        if entry_value <= 0:
            return False
        pnl = size * (current_price - entry_price)
        loss_pct = abs(pnl) / entry_value
        return pnl < 0 and loss_pct >= pct

    def should_take_profit(
        self,
        entry_price: float,
        current_price: float,
        size: float,
        take_profit_pct: float | None = None,
    ) -> bool:
        """Check if a take-profit should be triggered.

        Parameters
        ----------
        entry_price:
            Original entry price.
        current_price:
            Current market price.
        size:
            Position size in shares.
        take_profit_pct:
            Profit threshold (decimal).  Defaults to
            ``self.default_take_profit_pct``.

        Returns
        -------
        bool
            True if the position should be taken off.
        """
        pct = take_profit_pct if take_profit_pct is not None else self.default_take_profit_pct
        entry_value = size * entry_price
        if entry_value <= 0:
            return False
        pnl = size * (current_price - entry_price)
        profit_pct = pnl / entry_value
        return pnl > 0 and profit_pct >= pct

    # ── Trade recording ────────────────────────────────────────────────────

    def record_trade(self, size: float, price: float, pnl: float = 0.0) -> None:
        """Record a completed trade and update running P&L."""
        self.trades.append({"size": size, "price": price, "pnl": pnl})
        self.current_capital += pnl
        self._daily_pnl += pnl
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital

    # ── Persistence helpers ────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialise state for persistence."""
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "peak_capital": self.peak_capital,
            "trade_count": len(self.trades),
            "position_size_pct": self.position_size_pct,
            "daily_pnl": self._daily_pnl,
        }
