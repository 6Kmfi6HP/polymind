"""
Execution bridge: converts PortfolioTargets into OrderIntents/CancelIntents.

Factor strategies produce PortfolioTargets; the bridge translates them into
executor-level intents with size capping, cash constraints, and slippage.
"""

from __future__ import annotations

from dataclasses import dataclass

from polymind.core.intents import CancelIntent, OrderIntent, OrderSide
from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.execution.fill_model import MarketSnapshot


@dataclass
class ExecutionBridgeConfig:
    """Configuration for the factor execution bridge."""

    default_slippage_bps: float = 5.0
    max_position_size: float = 1000.0
    min_size: float = 1.0


class FactorExecutionBridge:
    """Converts PortfolioTargets into OrderIntents for the executor layer."""

    def __init__(self, config: ExecutionBridgeConfig) -> None:
        self.config = config

    async def to_order_intents(
        self,
        target: PortfolioTarget,
        snapshot: MarketSnapshot,
        available_cash: float = 10_000.0,
    ) -> list[OrderIntent]:
        """Convert a PortfolioTarget into OrderIntents.

        Parameters
        ----------
        target:
            The desired portfolio position.
        snapshot:
            Market snapshot for price-aware sizing.
        available_cash:
            Available cash for order size limiting.

        Returns
        -------
        list[OrderIntent]
            One OrderIntent for LONG/SHORT targets, empty list otherwise.
        """
        side = self._direction_to_side(target.direction)
        if side is None:
            return []
        size = self._calculate_size(target.target_size, available_cash, snapshot)
        if size < self.config.min_size:
            return []
        return [
            OrderIntent(
                market_id=target.market_id,
                side=side,
                price=0.0,
                size=size,
                metadata={
                    "strategy": target.reason,
                    "confidence": target.confidence,
                    "rank": target.rank,
                    "slippage_bps": self.config.default_slippage_bps,
                },
            )
        ]

    async def to_cancel_intents(self, market_ids: list[str]) -> list[CancelIntent]:
        """Create CancelIntents for the given markets."""
        return [
            CancelIntent(market_id=mid, reason="factor-rebalance")
            for mid in market_ids
        ]

    def _calculate_size(
        self,
        target_size: float,
        available_cash: float,
        snapshot: MarketSnapshot | None = None,
    ) -> float:
        size = min(target_size, self.config.max_position_size)
        if snapshot is not None and snapshot.mid_price > 0:
            cash_limited = available_cash / snapshot.mid_price
            size = min(size, cash_limited)
        return size

    @staticmethod
    def _direction_to_side(direction: PositionDirection) -> OrderSide | None:
        if direction == PositionDirection.LONG:
            return OrderSide.BUY
        if direction == PositionDirection.SHORT:
            return OrderSide.SELL
        return None
