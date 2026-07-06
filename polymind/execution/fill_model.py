"""
Fill simulation assumptions for paper trading and backtesting.

A FillModel encapsulates the assumptions about how a limit order fills:
passive (waits in queue, may fill partially or fully) vs. taker (immediate
fill at executable price).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from polymind.core.intents import OrderIntent, OrderSide


class FillMode(Enum):
    """Execution mode for a fill simulation."""

    PASSIVE = auto()  # limit order, filled when price crosses
    TAKER = auto()  # marketable limit / immediate fill at bid/ask


@dataclass
class MarketSnapshot:
    """Minimal market snapshot for fill simulation."""

    market_id: str
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    mid_price: float
    timestamp: datetime


@dataclass
class FillModelConfig:
    """Configuration for a FillModel."""

    mode: FillMode = FillMode.PASSIVE
    maker_fee_rate: float = 0.0  # e.g. 0.001 for 0.1%
    taker_fee_rate: float = 0.003  # e.g. 0.003 for 0.3%
    slippage_bps: float = 0.0  # additional slippage for taker fills
    queue_position_pct: float = 0.5  # assumed queue position (0.0–1.0)
    partial_fill_probability: float = 0.0  # probability of partial fill per tick


@dataclass
class FillResult:
    """Outcome of a fill simulation."""

    filled: bool
    fill_price: float
    fill_size: float
    fee: float
    remaining_size: float
    timestamp: datetime


class FillModel:
    """Simulate fill outcomes for an order intent.

    In PASSIVE mode, fill depends on price crossing the spread and queue
    position.  In TAKER mode, fill is immediate at the executable price.
    """

    def __init__(self, config: FillModelConfig):
        self.config = config

    async def simulate(
        self,
        intent: OrderIntent,
        snapshot: MarketSnapshot,
    ) -> FillResult:
        """Return a FillResult based on the current snapshot."""
        if self.config.mode == FillMode.TAKER:
            return self._simulate_taker(intent, snapshot)
        return self._simulate_passive(intent, snapshot)

    def estimate_execution_price(
        self,
        side: OrderSide,
        snapshot: MarketSnapshot,
    ) -> float:
        """Return the estimated execution price for a marketable order."""
        base_price = snapshot.ask_price if side == OrderSide.BUY else snapshot.bid_price
        if self.config.slippage_bps:
            slippage_factor = self.config.slippage_bps / 10_000.0
            if side == OrderSide.BUY:
                return base_price * (1.0 + slippage_factor)
            else:
                return base_price * (1.0 - slippage_factor)
        return base_price

    def _simulate_taker(
        self,
        intent: OrderIntent,
        snapshot: MarketSnapshot,
    ) -> FillResult:
        """Simulate an immediate taker fill at the executable price."""
        fill_price = self.estimate_execution_price(intent.side, snapshot)
        fee_rate = self.config.taker_fee_rate
        fee = intent.size * fill_price * fee_rate
        return FillResult(
            filled=True,
            fill_price=fill_price,
            fill_size=intent.size,
            fee=fee,
            remaining_size=0.0,
            timestamp=snapshot.timestamp,
        )

    def _simulate_passive(
        self,
        intent: OrderIntent,
        snapshot: MarketSnapshot,
    ) -> FillResult:
        """Simulate a passive fill based on price crossing, queue position, and partial fills.

        1. If price has not crossed → no fill.
        2. If price has crossed, queue position determines whether the order is
           at the front of the queue (fills) or still waiting.
        3. If filling and ``partial_fill_probability > 0``, only a fraction of the
           order fills; the remainder stays as ``remaining_size``.
        """
        crossed = self._price_crossed(intent, snapshot)
        if not crossed:
            return FillResult(
                filled=False,
                fill_price=0.0,
                fill_size=0.0,
                fee=0.0,
                remaining_size=intent.size,
                timestamp=snapshot.timestamp,
            )

        # Queue position — at front?  front = queue_position_pct near 0.0
        if not self._queue_allows_fill(intent):
            return FillResult(
                filled=False,
                fill_price=0.0,
                fill_size=0.0,
                fee=0.0,
                remaining_size=intent.size,
                timestamp=snapshot.timestamp,
            )

        # Determine fill size (possibly partial)
        if self.config.partial_fill_probability > 0.0:
            fill_size = round(intent.size * (1.0 - self.config.partial_fill_probability), 8)
            remaining = intent.size - fill_size
        else:
            fill_size = intent.size
            remaining = 0.0

        fill_price = intent.price
        fee_rate = self.config.maker_fee_rate
        fee = fill_size * fill_price * fee_rate
        return FillResult(
            filled=True,
            fill_price=fill_price,
            fill_size=fill_size,
            fee=fee,
            remaining_size=remaining,
            timestamp=snapshot.timestamp,
        )

    def _queue_allows_fill(self, intent: OrderIntent) -> bool:
        """Deterministic check of whether the order is at the front of the queue.

        Uses ``queue_position_pct`` (0.0 = front, 1.0 = back).  The fill
        probability is ``1.0 - queue_position_pct``.  A deterministic hash of the
        intent produces a value in [0, 1) that is compared against that threshold
        so simulation results are reproducible across runs.

        At the extremes:
        - ``queue_position_pct == 0.0`` → always fills (front of queue).
        - ``queue_position_pct == 1.0`` → never fills (back of queue).
        """
        fill_prob = 1.0 - self.config.queue_position_pct
        if fill_prob >= 1.0:
            return True
        if fill_prob <= 0.0:
            return False
        return self._fill_determinant(intent) < fill_prob

    @staticmethod
    def _fill_determinant(intent: OrderIntent) -> float:
        """Deterministic value in [0, 1) derived from the intent for reproducible simulation."""
        raw = f"{intent.market_id}:{intent.side.value}:{intent.price}:{intent.size}"
        digest = hashlib.md5(raw.encode()).hexdigest()
        return int(digest[:8], 16) / 0xFFFFFFFF

    @staticmethod
    def _price_crossed(intent: OrderIntent, snapshot: MarketSnapshot) -> bool:
        """Check if the market price has crossed the order price."""
        if intent.side == OrderSide.BUY:
            return intent.price >= snapshot.ask_price
        else:
            return intent.price <= snapshot.bid_price
