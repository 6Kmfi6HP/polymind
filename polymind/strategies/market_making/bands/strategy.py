"""
Bands price-margin market-making strategy.

Produces StrategyIntent with discrete buy/sell band orders around the
mid price. Each band has an independent spread and size weight.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from polymind.core.intents import CancelIntent, OrderIntent, StrategyIntent, TimeInForce
from polymind.core.strategy import BaseMMStrategy, StrategyConfig
from polymind.execution.fill_model import MarketSnapshot
from polymind.strategies.market_making.bands.pricing import BandPricingConfig, compute_band_prices
from polymind.strategies.market_making.bands.sizing import BandSizingConfig, distribute_band_sizes


class BandsStrategy(BaseMMStrategy):
    """Bands price-margin market-making strategy.

    Places discrete band orders around the mid price. On each tick,
    cancels all existing orders and places an updated set of bands.
    """

    def __init__(
        self,
        pricing_config: Optional[BandPricingConfig] = None,
        sizing_config: Optional[BandSizingConfig] = None,
        config: Optional[StrategyConfig] = None,
    ):
        super().__init__(config)
        self.pricing_config = pricing_config or BandPricingConfig()
        self.sizing_config = sizing_config or BandSizingConfig()

    async def analyze(self, market: MarketSnapshot) -> Optional[StrategyIntent]:
        """Analyze a market snapshot and produce a StrategyIntent."""
        target_price = market.mid_price
        if target_price <= 0:
            return None

        prices = compute_band_prices(target_price, self.pricing_config)
        if not prices:
            return None

        band_sizes = distribute_band_sizes(self.pricing_config, self.sizing_config)
        now = datetime.now(timezone.utc)

        cancels = [
            CancelIntent(
                market_id=market.market_id,
                reason=f"Bands refresh @ {now.isoformat()}",
            )
        ]

        orders: list[OrderIntent] = []
        for side, price, band_idx in prices:
            size = band_sizes[band_idx]
            if size <= 0:
                continue
            orders.append(
                OrderIntent(
                    market_id=market.market_id,
                    side=side,
                    price=price,
                    size=size,
                    time_in_force=TimeInForce.GTC,
                )
            )

        return StrategyIntent(
            timestamp=now,
            strategy_name=self.name,
            orders=orders,
            cancels=cancels,
        )
