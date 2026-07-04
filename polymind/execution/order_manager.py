"""
OrderManager — centralized order lifecycle tracking.

Single source of truth for open orders, fills, and positions across
all strategies and executors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any

from polymind.core.fills import FillEvent
from polymind.core.intents import OrderIntent
from polymind.execution.order_identity import OrderIdentity


class OrderStatus(Enum):
    """Lifecycle status of a tracked order."""

    PENDING = auto()
    OPEN = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()


@dataclass
class TrackedOrder:
    """A single order tracked by the OrderManager."""

    identity: OrderIdentity
    intent: OrderIntent
    status: OrderStatus = OrderStatus.PENDING
    exchange_order_id: str | None = None
    filled_size: float = 0.0
    filled_value: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OrderManager:
    """Centralized order lifecycle manager.

    Tracks every order across its entire lifecycle, from creation
    through fill, cancel, or rejection. Also maintains a fill ledger
    and computes net positions per (market_id, outcome).
    """

    def __init__(self) -> None:
        self._orders: dict[str, TrackedOrder] = {}
        self._fills: list[FillEvent] = []

    # ── Order lifecycle ────────────────────────────────────────────────

    def add_order(
        self,
        identity: OrderIdentity,
        intent: OrderIntent,
        exchange_order_id: str | None = None,
    ) -> TrackedOrder:
        """Register a new order.

        Raises ``ValueError`` if an order with the same identity already
        exists.
        """
        key = identity.to_identity_string()
        if key in self._orders:
            raise ValueError(f"Order '{key}' already tracked")

        now = datetime.now(timezone.utc)
        order = TrackedOrder(
            identity=identity,
            intent=intent,
            status=OrderStatus.OPEN if exchange_order_id else OrderStatus.PENDING,
            exchange_order_id=exchange_order_id,
            created_at=now,
            updated_at=now,
        )
        self._orders[key] = order
        return order

    def update_status(
        self,
        identity_string: str,
        status: OrderStatus,
        filled_size: float = 0.0,
        filled_value: float = 0.0,
        exchange_order_id: str | None = None,
    ) -> TrackedOrder | None:
        """Update the status and fill info for a tracked order.

        Returns the updated order, or ``None`` if not found.
        """
        order = self._orders.get(identity_string)
        if order is None:
            return None

        order.status = status
        order.updated_at = datetime.now(timezone.utc)
        if filled_size > 0:
            order.filled_size = filled_size
        if filled_value > 0:
            order.filled_value = filled_value
        if exchange_order_id is not None:
            order.exchange_order_id = exchange_order_id
        return order

    def get_order(self, identity_string: str) -> TrackedOrder | None:
        """Look up an order by its identity string."""
        return self._orders.get(identity_string)

    def get_open_orders(
        self,
        market_id: str | None = None,
    ) -> list[TrackedOrder]:
        """Return all orders in OPEN or PARTIALLY_FILLED status.

        Optionally filtered by *market_id*.
        """
        result = []
        for order in self._orders.values():
            is_open = order.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)
            if is_open and (market_id is None or order.intent.market_id == market_id):
                result.append(order)
        return result

    def get_orders_by_strategy(self, strategy_name: str) -> list[TrackedOrder]:
        """Return all orders for a given strategy name."""
        return [o for o in self._orders.values() if o.identity.strategy_name == strategy_name]

    def cancel_order(self, identity_string: str) -> bool:
        """Mark an order as CANCELLED.

        Returns ``True`` if the order was found and cancelled.
        """
        order = self._orders.get(identity_string)
        if order is None:
            return False
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        return True

    def cancel_all(self, market_id: str | None = None) -> int:
        """Cancel all open orders, optionally for a single market.

        Returns the number of orders cancelled.
        """
        count = 0
        for order in self._orders.values():
            if order.status not in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED):
                continue
            if market_id is not None and order.intent.market_id != market_id:
                continue
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc)
            count += 1
        return count

    # ── Fill tracking ──────────────────────────────────────────────────

    def add_fill(self, fill: FillEvent) -> None:
        """Record a fill event."""
        self._fills.append(fill)

    def get_fills(self, market_id: str | None = None) -> list[FillEvent]:
        """Return fill events, optionally filtered by market."""
        if market_id is None:
            return list(self._fills)
        return [f for f in self._fills if f.market_id == market_id]

    # ── Position tracking ──────────────────────────────────────────────

    def get_position(self, market_id: str, outcome: str) -> float:
        """Net position for (market_id, outcome): positive = long."""
        net = 0.0
        for fill in self._fills:
            if fill.market_id == market_id and fill.outcome == outcome:
                if fill.side.value == "BUY":
                    net += fill.size
                else:
                    net -= fill.size
        return net

    def get_all_positions(self) -> dict[str, dict[str, float]]:
        """Return ``{market_id: {outcome: net_size}}`` for all positions."""
        positions: dict[str, dict[str, float]] = {}
        for fill in self._fills:
            if fill.market_id not in positions:
                positions[fill.market_id] = {}
            if fill.outcome not in positions[fill.market_id]:
                positions[fill.market_id][fill.outcome] = 0.0
            if fill.side.value == "BUY":
                positions[fill.market_id][fill.outcome] += fill.size
            else:
                positions[fill.market_id][fill.outcome] -= fill.size
        return positions

    # ── Summary ────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """Return aggregate metrics about tracked orders."""
        total = len(self._orders)
        open_count = sum(
            1
            for o in self._orders.values()
            if o.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)
        )
        filled = sum(1 for o in self._orders.values() if o.status == OrderStatus.FILLED)
        cancelled = sum(1 for o in self._orders.values() if o.status == OrderStatus.CANCELLED)
        return {
            "total_orders": total,
            "open": open_count,
            "filled": filled,
            "cancelled": cancelled,
            "total_fills": len(self._fills),
        }
