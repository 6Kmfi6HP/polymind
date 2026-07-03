"""
Classic market-making strategy: sell-only limit orders.

Places limit sell orders at a spread above the bid price. This is the
simplest MM strategy, used as the foundation for more complex workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from polymind.core.intents import CancelIntent, OrderIntent, OrderSide, StrategyIntent, TimeInForce
from polymind.core.strategy import BaseMMStrategy, StrategyConfig
from polymind.execution.fill_model import MarketSnapshot


@dataclass
class ClassicMMConfig:
    """Configuration for Classic MM strategy."""

    spread_pct: float = 0.02  # spread above bid
    order_size: float = 10.0
    num_levels: int = 3  # number of sell levels
    level_spacing_pct: float = 0.01  # spacing between levels


class ClassicMMStrategy(BaseMMStrategy):
    """Classic market-making strategy: sell limit orders at spread.

    Places multiple sell limit orders at ascending prices above the
    bid. On each tick, cancels all existing and places updated orders.
    """

    def __init__(
        self,
        config: StrategyConfig | None = None,
        mm_config: ClassicMMConfig | None = None,
    ):
        super().__init__(config)
        self.mm_config = mm_config or ClassicMMConfig()

    async def analyze(self, market: MarketSnapshot) -> StrategyIntent | None:
        """Analyze a market snapshot and produce a StrategyIntent."""
        bid_price = market.bid_price
        if bid_price <= 0:
            return None

        now = datetime.now(timezone.utc)

        cancels = [
            CancelIntent(
                market_id=market.market_id,
                reason=f"Classic MM refresh @ {now.isoformat()}",
            )
        ]

        orders: list[OrderIntent] = []
        for level in range(self.mm_config.num_levels):
            price = bid_price * (
                1.0 + self.mm_config.spread_pct + level * self.mm_config.level_spacing_pct
            )
            orders.append(
                OrderIntent(
                    market_id=market.market_id,
                    side=OrderSide.SELL,
                    price=round(price, 6),
                    size=self.mm_config.order_size,
                    time_in_force=TimeInForce.GTC,
                )
            )

        return StrategyIntent(
            timestamp=now,
            strategy_name=self.name,
            orders=orders,
            cancels=cancels,
        )
