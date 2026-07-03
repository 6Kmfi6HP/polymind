"""Position limits, rate limits, and loss limits for risk management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class PositionLimit:
    """Limit for a single market position."""

    market_id: str
    max_size: float = float("inf")
    max_notional: float = float("inf")
    min_size: float = 0.0


@dataclass
class OrderRateLimit:
    """Rate limit on order submissions."""

    max_orders_per_window: int = 10
    window_seconds: int = 60


@dataclass
class DailyLossLimit:
    """Maximum acceptable daily loss."""

    max_loss_amount: float = float("inf")
    max_loss_pct: float = 100.0


@dataclass
class ExposureLimit:
    """Exposure limits at portfolio and per-market level."""

    max_total_exposure: float = float("inf")
    max_per_market_pct: float = 100.0


@dataclass
class LimitsConfig:
    """Aggregate configuration for all risk limits."""

    positions: List[PositionLimit] = field(default_factory=list)
    order_rate: OrderRateLimit = field(default_factory=OrderRateLimit)
    daily_loss: DailyLossLimit = field(default_factory=DailyLossLimit)
    exposure: ExposureLimit = field(default_factory=ExposureLimit)


class LimitsManager:
    """Evaluates orders and trading activity against configured limits."""

    def __init__(self, config: LimitsConfig) -> None:
        self.config = config

    def check_position_size(self, market_id: str, size: float) -> bool:
        """Check if a position size is within limits for the given market."""
        limit = self._find_position_limit(market_id)
        if size < limit.min_size:
            return False
        if size > limit.max_size:
            return False
        return True

    def check_order_rate(self, recent_order_count: int) -> bool:
        """Check if the recent order count is within the rate limit."""
        return recent_order_count <= self.config.order_rate.max_orders_per_window

    def check_daily_loss(self, current_loss: float, pnl: float) -> bool:
        """Check if the current loss plus any new loss is within the daily limit."""
        additional_loss = max(0.0, -pnl)
        total_loss = current_loss + additional_loss
        return total_loss <= self.config.daily_loss.max_loss_amount

    def check_exposure(self, current_exposure: float, new_exposure: float) -> bool:
        """Check if total exposure including new position is within limits."""
        total = current_exposure + new_exposure
        if total > self.config.exposure.max_total_exposure:
            return False
        if new_exposure > 0 and self.config.exposure.max_total_exposure > 0:
            pct = (new_exposure / self.config.exposure.max_total_exposure) * 100
            if pct > self.config.exposure.max_per_market_pct:
                return False
        return True

    def check_all(
        self,
        market_id: str,
        size: float,
        order_count: int,
        current_loss: float,
        exposure: float,
    ) -> List[str]:
        """Run all checks and return a list of failed check descriptions."""
        failed: List[str] = []
        if not self.check_position_size(market_id, size):
            failed.append(f"position_size_exceeded:{market_id}")
        if not self.check_order_rate(order_count):
            failed.append("order_rate_exceeded")
        if not self.check_daily_loss(current_loss, 0.0):
            failed.append("daily_loss_exceeded")
        if not self.check_exposure(0.0, exposure):
            failed.append("exposure_exceeded")
        return failed

    def _find_position_limit(self, market_id: str) -> PositionLimit:
        """Find the position limit for a market, returning a permissive default if none found."""
        for pl in self.config.positions:
            if pl.market_id == market_id:
                return pl
        return PositionLimit(market_id=market_id)
