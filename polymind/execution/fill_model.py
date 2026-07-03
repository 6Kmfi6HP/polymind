"""
Fill simulation assumptions for paper trading and backtesting.

A FillModel encapsulates the assumptions about how a limit order fills:
passive (waits in queue, may fill partially or fully) vs. taker (immediate
fill at executable price).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional

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
        """Simulate a passive fill based on price crossing."""
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
        fill_price = intent.price
        fee_rate = self.config.maker_fee_rate
        fee = intent.size * fill_price * fee_rate
        return FillResult(
            filled=True,
            fill_price=fill_price,
            fill_size=intent.size,
            fee=fee,
            remaining_size=0.0,
            timestamp=snapshot.timestamp,
        )

    @staticmethod
    def _price_crossed(intent: OrderIntent, snapshot: MarketSnapshot) -> bool:
        """Check if the market price has crossed the order price."""
        if intent.side == OrderSide.BUY:
            return intent.price >= snapshot.ask_price
        else:
            return intent.price <= snapshot.bid_price
