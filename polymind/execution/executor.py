"""
In-memory paper/sandbox executor implementing IntentExecutor.

PaperExecutor simulates the order lifecycle entirely in memory using a
FillModel.  No exchange credentials or network access required.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import (
    CancelIntent,
    IntentExecutor,
    OrderIntent,
    StrategyIntent,
)
from polymind.core.ledger import EntryType, LedgerEntry
from polymind.execution.fill_model import FillModel, MarketSnapshot
from polymind.execution.order_identity import OrderIdentity
from polymind.execution.order_manager import OrderManager


class OrderStatus(Enum):
    """Lifecycle status of an order within the executor."""

    OPEN = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    CANCELLED = auto()


@dataclass
class OrderRecord:
    """Internal record of an order in the paper executor."""

    identity: OrderIdentity
    intent: OrderIntent
    status: OrderStatus
    created_at: datetime
    filled_size: float = 0.0
    filled_value: float = 0.0
    cancelled_size: float = 0.0
    last_tick: datetime | None = None


@dataclass
class PositionRecord:
    """Current position for a single market/outcome."""

    market_id: str
    outcome: str
    size: float  # positive = long, negative = short
    avg_entry: float
    realized_pnl: float


class PaperExecutor(IntentExecutor):
    """In-memory paper/sandbox executor.

    Maintains an internal order book, simulates fills via FillModel,
    and records FillEvents and LedgerEntries.  No exchange credentials
    or network access required.
    """

    def __init__(
        self,
        fill_model: FillModel,
        initial_cash: float = 10_000.0,
        loop_interval: int = 60,
        order_manager: OrderManager | None = None,
    ):
        self.fill_model = fill_model
        self.initial_cash = initial_cash
        self.cash: float = initial_cash
        self.orders: dict[str, OrderRecord] = {}
        self.fills: list[FillEvent] = []
        self.ledger: list[LedgerEntry] = []
        self.positions: dict[str, PositionRecord] = {}
        self.loop_interval = loop_interval
        self._current_snapshot: MarketSnapshot | None = None
        self._fill_counter: int = 0
        self._ledger_counter: int = 0
        self._order_manager = order_manager

    async def execute(self, intent: StrategyIntent) -> dict[str, Any]:
        """Process a StrategyIntent: place orders, cancel orders, simulate ticks.

        Returns a summary dict keyed by market_id.
        """
        results: dict[str, dict[str, Any]] = {}

        # Process cancellations first, then new orders
        for cancel in intent.cancels:
            await self._process_cancel(cancel, results)

        for order in intent.orders:
            await self._process_order(order, intent.strategy_name, results)

        # Simulate fills for open orders if we have a snapshot
        if self._current_snapshot is not None and self.get_open_order_count() > 0:
            await self.simulate_tick(self._current_snapshot)

        # Build per-market summary
        summary: dict[str, Any] = {}
        for market_id, data in results.items():
            summary[market_id] = data

        # Include markets with orders but no results yet
        for record in self.orders.values():
            market = record.intent.market_id
            if market not in summary:
                summary[market] = {
                    "orders_placed": 0,
                    "fills": 0,
                    "filled_size": 0.0,
                    "cancelled": 0,
                }

        return summary

    async def simulate_tick(self, snapshot: MarketSnapshot) -> int:
        """Simulate one market-data tick for all open orders.

        Returns the number of fills that occurred.
        """
        self._current_snapshot = snapshot
        fill_count = 0

        # Collect open order IDs to avoid mutation during iteration
        open_ids = [
            oid_str for oid_str, record in self.orders.items() if record.status == OrderStatus.OPEN
        ]

        for oid_str in open_ids:
            record = self.orders.get(oid_str)
            if record is None or record.status != OrderStatus.OPEN:
                continue

            result = await self.fill_model.simulate(record.intent, snapshot)
            if result.filled and result.fill_size > 0:
                self._record_fill(record, result)
                fill_count += 1

        return fill_count

    def get_position(self, market_id: str) -> PositionRecord | None:
        """Return current position for a market (paper)."""
        # Position key is market_id (single-outcome simplified)
        return self.positions.get(market_id)

    def get_open_order_count(self) -> int:
        """Return number of currently open orders."""
        return sum(1 for record in self.orders.values() if record.status == OrderStatus.OPEN)

    async def shutdown(self) -> None:
        """Release executor resources and clear state."""
        self.orders.clear()
        self.fills.clear()
        self.ledger.clear()
        self.positions.clear()
        self.cash = self.initial_cash
        self._current_snapshot = None

    # ── Internal helpers ─────────────────────────────────────────────────

    def _make_identity(self, order: OrderIntent, strategy_name: str) -> OrderIdentity:
        """Derive an OrderIdentity from an OrderIntent."""
        return OrderIdentity(
            strategy_name=strategy_name,
            market_id=order.market_id,
            side=order.side,
            price=order.price,
            outcome=order.outcome,
            client_id=f"{strategy_name}:{order.market_id}:{order.side.value}:{order.price}",
        )

    async def _process_order(
        self,
        order: OrderIntent,
        strategy_name: str,
        results: dict[str, dict[str, Any]],
    ) -> None:
        """Process a single OrderIntent."""
        identity = self._make_identity(order, strategy_name)
        oid_str = identity.to_identity_string()

        # Dedupe: skip if already tracked
        if oid_str in self.orders:
            return

        # Budget enforcement: reject BUY orders that exceed available cash
        if order.side.value == "BUY":
            required_cash = order.price * order.size
            if required_cash > self.cash:
                return  # silently skip — budget exceeded

        record = OrderRecord(
            identity=identity,
            intent=order,
            status=OrderStatus.OPEN,
            created_at=datetime.now(timezone.utc),
        )
        self.orders[oid_str] = record

        # Track in OrderManager if configured
        if self._order_manager is not None:
            self._order_manager.add_order(identity, order)

        market = order.market_id
        if market not in results:
            results[market] = {"orders_placed": 0, "fills": 0, "filled_size": 0.0, "cancelled": 0}
        results[market]["orders_placed"] += 1

        # If we have a snapshot, try immediate fill
        if self._current_snapshot is not None:
            fill_result = await self.fill_model.simulate(order, self._current_snapshot)
            if fill_result.filled and fill_result.fill_size > 0:
                self._record_fill(record, fill_result)
                results[market]["fills"] += 1
                results[market]["filled_size"] += fill_result.fill_size

    async def _process_cancel(
        self,
        cancel: CancelIntent,
        results: dict[str, dict[str, Any]],
    ) -> None:
        """Process a single CancelIntent."""
        market = cancel.market_id
        if market not in results:
            results[market] = {"orders_placed": 0, "fills": 0, "filled_size": 0.0, "cancelled": 0}

        if cancel.order_id is not None:
            # Cancel a specific order
            record = self.orders.get(cancel.order_id)
            if record is not None and record.status == OrderStatus.OPEN:
                record.status = OrderStatus.CANCELLED
                results[market]["cancelled"] += 1
        else:
            # Cancel all open orders for this market
            for record in self.orders.values():
                if record.intent.market_id == market and record.status == OrderStatus.OPEN:
                    record.status = OrderStatus.CANCELLED
                    results[market]["cancelled"] += 1

    def _record_fill(self, record: OrderRecord, fill_result: Any) -> None:
        """Record a fill: update order, record FillEvent + LedgerEntry, update position."""
        self._fill_counter += 1
        fill_id = f"fill-{self._fill_counter:06d}"

        # Update order record
        record.status = OrderStatus.FILLED
        record.filled_size = fill_result.fill_size
        record.filled_value = fill_result.fill_price * fill_result.fill_size
        record.last_tick = fill_result.timestamp

        # Create FillEvent
        event = FillEvent(
            fill_id=fill_id,
            market_id=record.intent.market_id,
            outcome=record.intent.outcome or "YES",
            side=record.intent.side,
            price=fill_result.fill_price,
            size=fill_result.fill_size,
            fee=fill_result.fee,
            timestamp=fill_result.timestamp,
            source=FillSource.SIMULATED,
        )
        self.fills.append(event)

        # Track fill in OrderManager if configured
        if self._order_manager is not None:
            self._order_manager.add_fill(event)

        # Update cash
        trade_value = fill_result.fill_price * fill_result.fill_size
        direction = -1 if record.intent.side.value == "BUY" else 1
        cash_delta = direction * (trade_value - fill_result.fee)
        self.cash += cash_delta

        # Update position
        pos_key = record.intent.market_id
        current_pos = self.positions.get(pos_key)
        size_delta = (
            fill_result.fill_size if record.intent.side.value == "BUY" else -fill_result.fill_size
        )

        if current_pos is None:
            self.positions[pos_key] = PositionRecord(
                market_id=pos_key,
                outcome=record.intent.outcome or "YES",
                size=size_delta,
                avg_entry=fill_result.fill_price,
                realized_pnl=0.0,
            )
        else:
            old_size = current_pos.size
            new_size = old_size + size_delta

            # Calculate realized PnL if position flips or reduces
            if old_size * new_size < 0 or abs(new_size) < abs(old_size):
                # Partial or full close
                close_size = min(abs(old_size), abs(size_delta))
                if old_size > 0:  # closing a long
                    realized = (fill_result.fill_price - current_pos.avg_entry) * close_size
                else:  # closing a short
                    realized = (current_pos.avg_entry - fill_result.fill_price) * close_size
                current_pos.realized_pnl += realized

            # Update avg entry for remaining position
            if new_size == 0:
                current_pos.size = 0
                current_pos.avg_entry = 0.0
            elif old_size * new_size > 0:
                # Same direction, blend avg entry
                current_pos.avg_entry = (
                    old_size * current_pos.avg_entry + size_delta * fill_result.fill_price
                ) / new_size
                current_pos.size = new_size
            else:
                # Flips or reduces — position is now new direction
                current_pos.size = new_size
                current_pos.avg_entry = fill_result.fill_price

        # Create LedgerEntry
        self._ledger_counter += 1
        ledger = LedgerEntry(
            entry_id=f"ledger-{self._ledger_counter:06d}",
            entry_type=EntryType.FILL,
            timestamp=fill_result.timestamp,
            market_id=record.intent.market_id,
            description=(
                f"{record.intent.side.value} {fill_result.fill_size} @ {fill_result.fill_price}"
            ),
            delta_cash=cash_delta,
            delta_position=size_delta,
            position_after=self.positions.get(
                pos_key,
                PositionRecord(
                    market_id=pos_key, outcome="", size=0.0, avg_entry=0.0, realized_pnl=0.0
                ),
            ).size,
            cash_after=self.cash,
            fill_ref=fill_id,
        )
        self.ledger.append(ledger)
