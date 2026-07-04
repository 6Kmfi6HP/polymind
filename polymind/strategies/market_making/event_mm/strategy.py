"""
Event MM strategy — event-driven market making triggered by external signals.

Monitors for events (news, price movements, on-chain activity) and places
market-making orders around the event trigger. Strategy acts as the backend
for the Event MM workflow state machine.
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
class EventMMConfig:
    """Configuration for Event MM strategy.

    Parameters
    ----------
    spread_pct:
        Spread above/below mid price to place orders after trigger.
    order_size:
        Number of shares per order.
    cooldown_seconds:
        Seconds to wait after an event before re-entering watching state.
    bid_skew:
        Skew bid price downward (fraction of spread) during triggered state.
    ask_skew:
        Skew ask price upward (fraction of spread) during triggered state.
    """

    spread_pct: float = 0.05
    order_size: float = 10.0
    cooldown_seconds: int = 300
    bid_skew: float = 0.3
    ask_skew: float = 0.3


class EventMMStrategy(BaseMMStrategy):
    """Event-driven market-making strategy.

    In normal (watching) state, tight quotes around the mid price.
    When a trigger event arrives, widens the spread and skews prices
    to manage risk during volatility.
    """

    def __init__(
        self,
        config: StrategyConfig | None = None,
        mm_config: EventMMConfig | None = None,
    ):
        super().__init__(config)
        self.mm_config = mm_config or EventMMConfig()
        self._last_event: datetime | None = None
        self._is_triggered: bool = False

    @property
    def in_cooldown(self) -> bool:
        if self._last_event is None:
            return False
        elapsed = (datetime.now(timezone.utc) - self._last_event).total_seconds()
        return elapsed < self.mm_config.cooldown_seconds

    def set_triggered(self, triggered: bool = True) -> None:
        self._is_triggered = triggered

    async def analyze(self, market: MarketSnapshot) -> StrategyIntent | None:
        if market.bid_price <= 0 or market.ask_price <= 0:
            return None

        now = datetime.now(timezone.utc)
        mid = market.mid_price
        spread = mid * self.mm_config.spread_pct

        if self._is_triggered:
            bid_price = mid - spread * (1.0 + self.mm_config.bid_skew)
            ask_price = mid + spread * (1.0 + self.mm_config.ask_skew)
        else:
            bid_price = mid - spread * 0.5
            ask_price = mid + spread * 0.5

        cancels = [
            CancelIntent(
                market_id=market.market_id,
                reason=f"EventMM refresh @ {now.isoformat()}",
            ),
        ]

        orders = [
            OrderIntent(
                market_id=market.market_id,
                side=OrderSide.BUY,
                price=round(bid_price, 6),
                size=self.mm_config.order_size,
                time_in_force=TimeInForce.GTC,
            ),
            OrderIntent(
                market_id=market.market_id,
                side=OrderSide.SELL,
                price=round(ask_price, 6),
                size=self.mm_config.order_size,
                time_in_force=TimeInForce.GTC,
            ),
        ]

        return StrategyIntent(
            timestamp=now,
            strategy_name=self.name,
            orders=orders,
            cancels=cancels,
        )
