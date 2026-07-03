"""
Execution models for backtesting with realistic market simulation.

Provides PassiveExecutionModel (queue-based limit order fills) and
TakerExecutionModel (immediate fill with slippage) that produce FillResult
objects for the backtest engine.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from polymind.core.intents import OrderIntent, OrderSide
from polymind.execution.fill_model import FillResult, MarketSnapshot


@dataclass
class ExecutionModelConfig:
    """Configuration for execution model behaviour.

    Attributes:
        slippage_bps: Additional slippage in basis points for taker orders.
        latency_ms: Simulated latency in milliseconds for order placement.
        partial_fill_prob: Probability (0.0–1.0) of a partial fill per tick
            when the order is at the front of the queue.
        queue_position_pct: Assumed position in the order queue (0.0 = front,
            1.0 = back). Used by PassiveExecutionModel as a baseline.
    """

    slippage_bps: float = 0.0
    latency_ms: float = 0.0
    partial_fill_prob: float = 0.0
    queue_position_pct: float = 0.0


class PassiveExecutionModel:
    """Simulate limit order fills based on price crossing and queue position.

    An order fills passively when the market price crosses the limit price
    and the order has advanced to the front of the queue.  Partial fills
    occur probabilistically based on ``partial_fill_prob`` in the config.
    """

    def __init__(self, config: ExecutionModelConfig) -> None:
        self.config = config

    def simulate_fill(
        self,
        intent: OrderIntent,
        snapshot: MarketSnapshot,
    ) -> FillResult:
        """Determine if a passive limit order would fill given the snapshot.

        A fill occurs when:

        1. The market price has crossed the limit price, AND
        2. The order's queue position has reached the front (probabilistic).

        Partial fills occur with probability ``partial_fill_prob``.
        """
        if not self._price_crossed(intent, snapshot):
            return FillResult(
                filled=False,
                fill_price=0.0,
                fill_size=0.0,
                fee=0.0,
                remaining_size=intent.size,
                timestamp=snapshot.timestamp,
            )

        # Queue position determines fill likelihood
        queue_pos = self.estimate_queue_position(intent.price, snapshot)
        if queue_pos > 0.0 and random.random() < queue_pos:
            return FillResult(
                filled=False,
                fill_price=0.0,
                fill_size=0.0,
                fee=0.0,
                remaining_size=intent.size,
                timestamp=snapshot.timestamp,
            )

        # Price has crossed and order is at front -- fill (possibly partial)
        if random.random() < self.config.partial_fill_prob:
            fill_size = round(intent.size * (1.0 - self.config.partial_fill_prob), 8)
            remaining = intent.size - fill_size
        else:
            fill_size = intent.size
            remaining = 0.0

        fill_price = intent.price
        fee = fill_size * fill_price * 0.0  # maker fee (configurable later)
        return FillResult(
            filled=True,
            fill_price=fill_price,
            fill_size=fill_size,
            fee=fee,
            remaining_size=remaining,
            timestamp=snapshot.timestamp,
        )

    def estimate_queue_position(
        self,
        price_level: float,
        snapshot: MarketSnapshot,
    ) -> float:
        """Estimate queue position (0.0–1.0) based on price and book depth.

        Returns a value in [0.0, 1.0] where 0.0 means the order is at the
        front of the queue and 1.0 means the back.  The estimate uses the
        configured ``queue_position_pct`` as a baseline and adjusts it
        according to how aggressive the price is relative to total depth.

        When book depth is zero or negative the raw config value is used.
        """
        book_depth = snapshot.ask_size + snapshot.bid_size
        if book_depth <= 0:
            return self.config.queue_position_pct

        # More aggressive pricing (deeper relative position) improves
        # queue position.  Scale inversely with book depth.
        adjusted = self.config.queue_position_pct * (1.0 / (1.0 + book_depth))
        return min(1.0, max(0.0, adjusted))

    @staticmethod
    def _price_crossed(intent: OrderIntent, snapshot: MarketSnapshot) -> bool:
        """Check if the market price has crossed the order price."""
        if intent.side == OrderSide.BUY:
            return intent.price >= snapshot.ask_price
        return intent.price <= snapshot.bid_price


class TakerExecutionModel:
    """Simulate immediate taker fills with slippage.

    Taker orders fill immediately at the best available price, adjusted for
    slippage based on order size relative to book liquidity.
    """

    def __init__(self, config: ExecutionModelConfig) -> None:
        self.config = config

    def simulate_fill(
        self,
        intent: OrderIntent,
        snapshot: MarketSnapshot,
    ) -> FillResult:
        """Simulate an immediate taker fill.

        The fill price is the best available price (ask for BUY, bid for
        SELL) plus slippage estimated from the order size and market
        liquidity.
        """
        book_liquidity = snapshot.ask_size if intent.side == OrderSide.BUY else snapshot.bid_size
        additional_slippage = self.estimate_slippage(intent.size, book_liquidity)
        total_slippage_bps = self.config.slippage_bps + additional_slippage
        base_price = snapshot.ask_price if intent.side == OrderSide.BUY else snapshot.bid_price

        slippage_factor = total_slippage_bps / 10_000.0
        if intent.side == OrderSide.BUY:
            fill_price = base_price * (1.0 + slippage_factor)
        else:
            fill_price = base_price * (1.0 - slippage_factor)

        fee = intent.size * fill_price * 0.003  # taker fee
        return FillResult(
            filled=True,
            fill_price=fill_price,
            fill_size=intent.size,
            fee=fee,
            remaining_size=0.0,
            timestamp=snapshot.timestamp,
        )

    def estimate_slippage(
        self,
        size: float,
        book_liquidity: float,
    ) -> float:
        """Estimate additional slippage in basis points for a taker order.

        Larger orders relative to available liquidity incur more slippage.
        Returns additional bps (beyond ``slippage_bps`` in config).

        * ``size / book_liquidity <= 0.1``: no additional slippage
        * ``<= 0.5``: linear up to 2.5 bps
        * ``<= 1.0``: linear up to 10 bps
        * ``> 1.0``: capped at 20 bps
        """
        if book_liquidity <= 0 or size <= 0:
            return 0.0
        ratio = size / book_liquidity
        if ratio <= 0.1:
            return 0.0
        if ratio <= 0.5:
            return ratio * 5.0  # up to 2.5 bps
        if ratio <= 1.0:
            return ratio * 10.0  # up to 10 bps
        return 20.0  # capped at 20 bps for very large orders
