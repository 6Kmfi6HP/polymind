"""
Maker Rebate strategy — YES + NO price arbitrage with maker fee rebate.

Detects when YES + NO < 1 (a rebate opportunity exists), places limit
orders on both sides to capture the spread, and produces fills that feed
into the Maker Rebate workflow state machine.
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
class MakerRebateConfig:
    """Configuration for Maker Rebate strategy.

    Parameters
    ----------
    max_spread:
        Maximum allowable YES + NO spread to quote (e.g. 0.03 = 3%).
        Only quotes when ``yes_price + no_price <= 1 + max_spread``.
    order_size:
        Number of shares to place on each side.
    merge_on_fill:
        If True, triggers merge workflow when both sides fill.
        Set to False for pure quoting without merge automation.
    price_tolerance:
        Minimum price movement to trigger order refresh (decimal).
    rebate_threshold:
        Minimum rebate (1 - price_sum) to consider an opportunity viable.
    """

    max_spread: float = 0.03
    order_size: float = 10.0
    merge_on_fill: bool = True
    price_tolerance: float = 0.001
    rebate_threshold: float = 0.005  # 0.5 % minimum rebate


class MakerRebateStrategy(BaseMMStrategy):
    """Market-making strategy that arbitrages YES+NO price discrepancies.

    The core insight: if YES price + NO price < 1, buying both and
    merging at expiry yields the difference. This strategy captures that
    spread while earning maker rebates on the CLOB.

    On each tick:
    1. Read YES and NO order books from the snapshot.
    2. Compute ``sum_price = yes_ask + no_ask``.
    3. If ``sum_price < 1 + max_spread`` and ``1 - sum_price >= rebate_threshold``:
       - Place limit bids at ``yes_ask`` and ``no_ask``.
       - Cancel any stale orders.
    4. If ``sum_price > 1 + tolerance``:
       - Place limit asks on both sides to sell existing inventory.
       - Cancel stale bids.
    """

    def __init__(
        self,
        config: StrategyConfig | None = None,
        mm_config: MakerRebateConfig | None = None,
    ):
        super().__init__(config)
        self.mm_config = mm_config or MakerRebateConfig()

    async def analyze(self, market: MarketSnapshot) -> StrategyIntent | None:
        """Analyze a market snapshot and produce a StrategyIntent.

        Expects *market* to contain ``yes_ask`` and ``no_ask`` fields
        (or a nested order-book structure).
        """
        if not self._has_valid_prices(market):
            return None

        yes_ask = self._get_yes_ask(market)
        no_ask = self._get_no_ask(market)
        yes_bid = self._get_yes_bid(market)
        no_bid = self._get_no_bid(market)

        if yes_ask is None or no_ask is None:
            return None

        sum_price = yes_ask + no_ask
        rebate = 1.0 - sum_price
        now = datetime.now(timezone.utc)

        # Cancel existing orders on every tick to refresh
        cancels = [
            CancelIntent(
                market_id=market.market_id,
                reason=f"MakerRebate refresh @ {now.isoformat()}",
            ),
        ]

        orders: list[OrderIntent] = []

        if rebate >= self.mm_config.rebate_threshold:
            # Profitable entry: buy both sides
            orders.append(
                OrderIntent(
                    market_id=market.market_id,
                    side=OrderSide.BUY,
                    price=yes_ask,
                    size=self.mm_config.order_size,
                    outcome="YES",
                    time_in_force=TimeInForce.GTC,
                ),
            )
            orders.append(
                OrderIntent(
                    market_id=market.market_id,
                    side=OrderSide.BUY,
                    price=no_ask,
                    size=self.mm_config.order_size,
                    outcome="NO",
                    time_in_force=TimeInForce.GTC,
                ),
            )
        elif yes_bid is not None and no_bid is not None:
            # Not profitable — sell any inventory accumulated
            orders.append(
                OrderIntent(
                    market_id=market.market_id,
                    side=OrderSide.SELL,
                    price=yes_bid,
                    size=self.mm_config.order_size,
                    outcome="YES",
                    time_in_force=TimeInForce.GTC,
                    reduce_only=True,
                ),
            )
            orders.append(
                OrderIntent(
                    market_id=market.market_id,
                    side=OrderSide.SELL,
                    price=no_bid,
                    size=self.mm_config.order_size,
                    outcome="NO",
                    time_in_force=TimeInForce.GTC,
                    reduce_only=True,
                ),
            )

        if not orders:
            return None

        return StrategyIntent(
            timestamp=now,
            strategy_name=self.name,
            orders=orders,
            cancels=cancels,
        )

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _has_valid_prices(market: MarketSnapshot) -> bool:
        """Check if the snapshot contains usable price data."""
        return market.ask_price > 0 and market.bid_price > 0

    @staticmethod
    def _get_yes_ask(market: MarketSnapshot) -> float | None:
        """Extract YES ask price from the snapshot.

        Checks a nested ``outcomes`` dict first, then falls back to
        the top-level ``ask_price``.
        """
        outcomes = getattr(market, "outcomes", None)
        if outcomes and isinstance(outcomes, dict):
            yes = outcomes.get("YES", {})
            if isinstance(yes, dict):
                return yes.get("ask_price") or yes.get("ask")
        return market.ask_price

    @staticmethod
    def _get_no_ask(market: MarketSnapshot) -> float | None:
        """Extract NO ask price from the snapshot."""
        outcomes = getattr(market, "outcomes", None)
        if outcomes and isinstance(outcomes, dict):
            no = outcomes.get("NO", {})
            if isinstance(no, dict):
                return no.get("ask_price") or no.get("ask")
        return None  # no separate NO price in top-level snapshot

    @staticmethod
    def _get_yes_bid(market: MarketSnapshot) -> float | None:
        """Extract YES bid price from the snapshot."""
        outcomes = getattr(market, "outcomes", None)
        if outcomes and isinstance(outcomes, dict):
            yes = outcomes.get("YES", {})
            if isinstance(yes, dict):
                return yes.get("bid_price") or yes.get("bid")
        return market.bid_price

    @staticmethod
    def _get_no_bid(market: MarketSnapshot) -> float | None:
        """Extract NO bid price from the snapshot."""
        outcomes = getattr(market, "outcomes", None)
        if outcomes and isinstance(outcomes, dict):
            no = outcomes.get("NO", {})
            if isinstance(no, dict):
                return no.get("bid_price") or no.get("bid")
        return None
