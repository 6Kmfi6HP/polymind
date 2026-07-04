# Phase 28: OrderManager — Implementation Plan

**Date:** 2026-07-04

---

### Task 1: Create OrderManager

**File:** `polymind/execution/order_manager.py`

Types:
- `OrderStatus` enum: PENDING, OPEN, PARTIALLY_FILLED, FILLED, CANCELLED, REJECTED
- `TrackedOrder` dataclass: identity, intent, status, exchange_order_id, filled_size, filled_value, created_at, updated_at
- `OrderManager` class with methods as designed

### Task 2: Tests

**File:** `tests/execution/test_order_manager.py`

Test cases (15+):
- add_order, get_order
- update_status lifecycle
- get_open_orders filtering
- get_orders_by_strategy
- cancel_order and cancel_all
- add_fill, get_fills
- get_position, get_all_positions
- summary
- duplicate identity handling

### Task 3: Wire + full suite
