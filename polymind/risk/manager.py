"""
Risk management — position limits, Kelly sizing, drawdown protection.
"""

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
    """Manages trading risk — exposure, sizing, and drawdown."""

    def __init__(self, initial_capital: float = 1000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_capital = initial_capital
        self.trades: list = []
        self._daily_loss = 0.0

    def calculate_position_size(
        self,
        price: float,
        confidence: float = 0.5,
        method: str = "manual",
        kelly_fraction: float = 0.25,
    ) -> float:
        """Calculate position size using the specified method."""
        if method == "kelly":
            # Kelly: f* = (p*b - q) / b
            b = (1 - price) / price  # odds
            p = confidence
            q = 1 - p
            kelly = (p * b - q) / b if b > 0 else 0
            return max(0, kelly * self.current_capital * kelly_fraction)
        return 0.0

    def can_open_position(self, size: float, price: float) -> bool:
        """Check if a new position can be opened given risk limits."""
        return size <= self.current_capital * 0.1

    def record_trade(self, size: float, price: float) -> None:
        """Record a completed trade."""
        self.trades.append({"size": size, "price": price})

    def to_dict(self) -> dict[str, Any]:
        """Serialise state for persistence."""
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "peak_capital": self.peak_capital,
            "trade_count": len(self.trades),
        }
