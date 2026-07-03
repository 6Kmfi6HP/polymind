"""
Order intents and executor protocol (ADR 0002).

Strategies produce intents; executors own CLOB transport, retries, and
cancellations. This layer is the contract between strategy policy and
exchange-specific implementation.

Intent types are plain dataclasses so risk gates can inspect them before
execution, and strategy modules remain testable from immutable snapshots.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional


# ── Enums ─────────────────────────────────────────────────────────────────


class IntentType(Enum):
    """High-level category of an intent."""

    PLACE_ORDER = auto()
    CANCEL_ORDER = auto()
    CANCEL_ALL = auto()
    HOLD = auto()
    CLOSE_POSITION = auto()


class OrderSide(Enum):
    """CLOB order side."""

    BUY = "BUY"
    SELL = "SELL"


class TimeInForce(Enum):
    """Order time-in-force instructions."""

    GTC = "GTC"  # Good-Till-Cancelled
    IOC = "IOC"  # Immediate-Or-Cancel
    FOK = "FOK"  # Fill-Or-Kill


# ── Intent types ──────────────────────────────────────────────────────────


@dataclass
class OrderIntent:
    """
    Intent to place a limit order on the CLOB.

    Market-making strategies produce one or more OrderIntents per tick.
    The executor is responsible for translating these into SDK calls,
    handling partial fills, retries, and cancellations.
    """

    market_id: str
    side: OrderSide
    price: float
    size: float
    outcome: Optional[str] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    expiration: Optional[datetime] = None
    reduce_only: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CancelIntent:
    """
    Intent to cancel one or more open orders.

    When ``order_id`` is ``None`` the executor should cancel **all** open
    orders for the given market.  This is the common case after a price
    shift where the entire order ladder is replaced.
    """

    market_id: str
    order_id: Optional[str] = None
    reason: str = ""


@dataclass
class StrategyIntent:
    """
    Complete output of a strategy's analysis tick.

    A strategy processes market snapshots and produces a StrategyIntent
    containing the orders it wants placed and the orders it wants
    cancelled.  Risk gates inspect this before the executor acts on it.

    The ``risk_override`` field lets strategies communicate dynamic risk
    adjustments (e.g. "reduce size by 50 % during earnings") without
    coupling strategy logic to the risk manager API.
    """

    timestamp: datetime
    strategy_name: str
    orders: List[OrderIntent] = field(default_factory=list)
    cancels: List[CancelIntent] = field(default_factory=list)
    risk_override: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Return True when no work needs doing."""
        return not self.orders and not self.cancels


# ── Executor protocol ─────────────────────────────────────────────────────


class IntentExecutor(ABC):
    """
    Abstract executor that consumes StrategyIntents.

    Implementations wrap the Polymarket CLOB SDK (or a paper/simulated
    engine) and own all exchange-specific concerns: transport, retry,
    error mapping, fill tracking, and order-state mutation.

    Subclasses must implement :meth:`execute` and may override
    :meth:`dry_run` for preflight simulation.
    """

    @abstractmethod
    async def execute(self, intent: StrategyIntent) -> Dict[str, Any]:
        """
        Execute the given intent against the exchange.

        Returns a result dict keyed by market_id with per-order outcomes:
        ``{"order_id": ..., "status": ..., "filled_size": ...}``.
        """
        ...

    async def dry_run(self, intent: StrategyIntent) -> Dict[str, Any]:
        """
        Simulate execution without placing real orders.

        Base implementation logs the intent and returns an empty result.
        Subclasses may override with order-book simulation.
        """
        _log_intent(intent)
        return {"dry_run": True, "orders_proposed": len(intent.orders)}

    async def shutdown(self) -> None:
        """Release executor resources (connections, timers)."""
        pass


def _log_intent(intent: StrategyIntent) -> None:
    """Log a StrategyIntent in a structured way (internal helper)."""
    import logging

    logger = logging.getLogger("polymind.intents")
    logger.info(
        "Intent [%s] %s — %d orders, %d cancels",
        intent.strategy_name,
        intent.timestamp.isoformat(),
        len(intent.orders),
        len(intent.cancels),
    )
