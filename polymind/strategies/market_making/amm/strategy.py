"""
AMM concentrated-liquidity market-making strategy.

Produces StrategyIntent with symmetric buy/sell ladder around the mid price.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from polymind.core.intents import CancelIntent, IntentType, OrderIntent, OrderSide, StrategyIntent, TimeInForce
from polymind.core.strategy import BaseMMStrategy, StrategyConfig
from polymind.execution.fill_model import MarketSnapshot
from polymind.strategies.market_making.amm.pricing import AMMPricingConfig, compute_ladder
from polymind.strategies.market_making.amm.sizing import AMMSizingConfig, distribute_size


class AMMStrategy(BaseMMStrategy):
    """AMM concentrated-liquidity market-making strategy.

    Places a symmetric ladder of buy/sell limit orders around the mid price.
    On each tick, cancels all existing orders and places an updated ladder.
    """

    def __init__(
        self,
        pricing_config: Optional[AMMPricingConfig] = None,
        sizing_config: Optional[AMMSizingConfig] = None,
        config: Optional[StrategyConfig] = None,
    ):
        super().__init__(config)
        self.pricing_config = pricing_config or AMMPricingConfig()
        self.sizing_config = sizing_config or AMMSizingConfig()

    async def analyze(self, market: MarketSnapshot) -> Optional[StrategyIntent]:
        """Analyze a market snapshot and produce a StrategyIntent.

        Cancels all open orders for this market, then places a new ladder
        centered on the mid price.
        """
        target_price = market.mid_price
        if target_price <= 0:
            return None

        ladder = compute_ladder(target_price, self.pricing_config)
        if not ladder:
            return None

        sizes = distribute_size(
            self.sizing_config.total_exposure,
            self.pricing_config.num_levels,
            self.sizing_config.concentration_pct,
        )

        now = datetime.now(timezone.utc)

        # Cancel all existing orders for this market
        cancels = [
            CancelIntent(
                market_id=market.market_id,
                reason=f"AMM ladder refresh @ {now.isoformat()}",
            )
        ]

        # Place new ladder orders
        orders: list[OrderIntent] = []
        for (side, price, level), size in zip(ladder, sizes * 2):
            if size <= 0:
                continue
            order = OrderIntent(
                market_id=market.market_id,
                side=side,
                price=price,
                size=size,
                time_in_force=TimeInForce.GTC,
            )
            orders.append(order)

        return StrategyIntent(
            timestamp=now,
            strategy_name=self.name,
            orders=orders,
            cancels=cancels,
        )
