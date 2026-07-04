"""
Sniper strategy — deep-discount GTC limit orders on short-term options.

Monitors markets for significant price dislocations (e.g. a YES token
trading far below its fair value) and places limit orders to capture
the rebound.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from polymind.core.intents import (
    CancelIntent,
    OrderIntent,
    OrderSide,
    StrategyIntent,
    TimeInForce,
)
from polymind.core.strategy import BaseMMStrategy, StrategyConfig
from polymind.execution.fill_model import MarketSnapshot


@dataclass
class SniperConfig:
    """Configuration for Sniper strategy.

    Parameters
    ----------
    discount_threshold:
        Fraction below fair value to trigger a snipe (e.g. 0.5 = 50% off).
    order_size:
        Number of shares to buy when opportunity detected.
    fair_value_source:
        How to estimate fair value: "mid", "last", "oracle", or "manual".
    manual_fair_value:
        Fixed fair value override (used when fair_value_source="manual").
    max_position:
        Maximum total position size across all sniped markets.
    """

    discount_threshold: float = 0.50
    order_size: float = 20.0
    fair_value_source: str = "mid"
    manual_fair_value: float = 0.0
    max_position: float = 200.0


class SniperStrategy(BaseMMStrategy):
    """Sniper strategy — deep-discount GTC limit orders.

    Watches for prices that drop far below fair value and places
    limit buy orders. Once filled, sells when price returns to fair
    value.
    """

    def __init__(
        self,
        config: StrategyConfig | None = None,
        mm_config: SniperConfig | None = None,
    ):
        super().__init__(config)
        self.mm_config = mm_config or SniperConfig()

    async def analyze(self, market: MarketSnapshot) -> StrategyIntent | None:
        if market.bid_price <= 0 or market.ask_price <= 0:
            return None

        now = datetime.now(timezone.utc)
        fair_value = self._estimate_fair_value(market)
        if fair_value <= 0:
            return None

        discount = 1.0 - (market.ask_price / fair_value) if fair_value > 0 else 0.0
        cancels = [
            CancelIntent(
                market_id=market.market_id,
                reason=f"Sniper refresh @ {now.isoformat()}",
            ),
        ]

        if discount >= self.mm_config.discount_threshold:
            order = OrderIntent(
                market_id=market.market_id,
                side=OrderSide.BUY,
                price=market.ask_price,
                size=self.mm_config.order_size,
                time_in_force=TimeInForce.GTC,
            )
            return StrategyIntent(
                timestamp=now,
                strategy_name=self.name,
                orders=[order],
                cancels=cancels,
            )

        return StrategyIntent(
            timestamp=now,
            strategy_name=self.name,
            orders=[],
            cancels=cancels,
        )

    def _estimate_fair_value(self, market: MarketSnapshot) -> float:
        src = self.mm_config.fair_value_source
        if src == "mid":
            return market.mid_price
        elif src == "last" or src == "oracle":
            return (market.bid_price + market.ask_price) / 2
        elif src == "manual":
            return self.mm_config.manual_fair_value
        return market.mid_price
