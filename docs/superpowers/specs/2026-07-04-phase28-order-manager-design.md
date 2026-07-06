> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 28: OrderManager — Centralized Order Lifecycle — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

The OrderManager provides centralized order lifecycle tracking across all strategies and executors. It is the single source of truth for open orders, fills, and positions.

## Existing contracts

- `OrderIdentity` in `polymind/execution/order_identity.py` — deterministic order identity
- `OrderIntent` / `CancelIntent` / `StrategyIntent` in `polymind/core/intents.py`
- `FillEvent` / `FillSource` in `polymind/core/fills.py`
- `PaperExecutor` in `polymind/execution/executor.py` — internal per-instance order tracking

## Design

### OrderManager

```python
@dataclass
class TrackedOrder:
    identity: OrderIdentity
    intent: OrderIntent
    status: OrderStatus  # PENDING, OPEN, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED
    exchange_order_id: str | None = None
    filled_size: float = 0.0
    filled_value: float = 0.0
    created_at: datetime
    updated_at: datetime

class OrderManager:
    def __init__(self):
        self._orders: dict[str, TrackedOrder] = {}  # identity_string -> order
        self._fills: list[FillEvent] = []

    def add_order(self, identity, intent) -> TrackedOrder
    def update_status(self, identity_string, status, filled_size=0) -> TrackedOrder | None
    def get_order(self, identity_string) -> TrackedOrder | None
    def get_open_orders(self, market_id=None) -> list[TrackedOrder]
    def get_orders_by_strategy(self, strategy_name) -> list[TrackedOrder]
    def get_fills(self, market_id=None) -> list[FillEvent]
    def add_fill(self, fill: FillEvent) -> None
    def cancel_order(self, identity_string) -> bool
    def cancel_all(self, market_id=None) -> int
    def get_position(self, market_id, outcome) -> float
    def get_all_positions(self) -> dict
    def summary(self) -> dict  # total_orders, open, filled, cancelled, total_fills
```

## Files
- `polymind/execution/order_manager.py`
- `tests/execution/test_order_manager.py`
