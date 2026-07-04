"""
Copy Trade strategy — mirrors target wallet trades in real-time.

Monitors a target wallet's Polymarket activity and replicates trades
proportionally based on the configured allocation ratio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
class TrackedTrade:
    """A trade detected from the target wallet."""

    market_id: str
    side: str
    price: float
    size: float
    outcome: str
    timestamp: datetime
    tx_hash: str = ""


@dataclass
class CopyTradeConfig:
    """Configuration for Copy Trade strategy.

    Parameters
    ----------
    target_wallet:
        Wallet address to monitor and replicate.
    allocation_ratio:
        Fraction of target's trade size to replicate (0.0–1.0).
    min_trade_size:
        Minimum trade size in USDC to replicate.
    max_trade_size:
        Maximum trade size per replicated order.
    supported_outcomes:
        List of outcomes to copy (e.g. ["YES", "NO"]).
    """

    target_wallet: str = ""
    allocation_ratio: float = 0.1
    min_trade_size: float = 1.0
    max_trade_size: float = 100.0
    supported_outcomes: list[str] = field(default_factory=lambda: ["YES", "NO"])


class CopyTradeStrategy(BaseMMStrategy):
    """Copy Trade strategy — replicates target wallet activity.

    The strategy holds a queue of detected trades. On each tick, it
    processes the queue and places orders matching the target wallet's
    activity at the specified allocation ratio.

    Trades are injected externally (from a WebSocket monitor or API
    scanner) via the ``add_trade()`` method.
    """

    def __init__(
        self,
        config: StrategyConfig | None = None,
        mm_config: CopyTradeConfig | None = None,
    ):
        super().__init__(config)
        self.mm_config = mm_config or CopyTradeConfig()
        self._pending_trades: list[TrackedTrade] = []
        self._processed: set[str] = set()

    def add_trade(self, trade: TrackedTrade) -> None:
        """Queue a detected trade for replication."""
        self._pending_trades.append(trade)

    async def analyze(self, market: MarketSnapshot) -> StrategyIntent | None:
        if not self._pending_trades:
            return None

        now = datetime.now(timezone.utc)
        orders: list[OrderIntent] = []

        cancels = [
            CancelIntent(
                market_id=market.market_id,
                reason=f"CopyTrade refresh @ {now.isoformat()}",
            ),
        ]

        remaining: list[TrackedTrade] = []
        for trade in self._pending_trades:
            dedup_key = f"{trade.tx_hash}:{trade.outcome}" if trade.tx_hash else id(trade)
            if dedup_key in self._processed:
                continue

            size = min(
                max(trade.size * self.mm_config.allocation_ratio, self.mm_config.min_trade_size),
                self.mm_config.max_trade_size,
            )

            if trade.market_id != market.market_id:
                remaining.append(trade)
                continue

            side = OrderSide.BUY if trade.side.upper() in ("BUY", "LONG") else OrderSide.SELL

            orders.append(
                OrderIntent(
                    market_id=trade.market_id,
                    side=side,
                    price=round(trade.price, 6),
                    size=size,
                    outcome=trade.outcome,
                    time_in_force=TimeInForce.IOC,
                ),
            )
            self._processed.add(dedup_key)

        self._pending_trades = remaining

        if not orders:
            return None

        return StrategyIntent(
            timestamp=now,
            strategy_name=self.name,
            orders=orders,
            cancels=cancels,
        )
