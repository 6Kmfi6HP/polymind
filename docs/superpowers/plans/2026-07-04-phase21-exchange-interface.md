# Phase 21: Multi-Exchange Adapter Interface — Implementation Plan

---

### Task 1: Create exchange adapter interface

**File:** `polymind/core/exchange.py`

Define abstract `ExchangeAdapter` with:
- `connect()`, `close()` — lifecycle
- `get_markets()`, `get_order_book()` — market data
- `place_order()`, `cancel_order()`, `cancel_all_orders()` — trading
- `get_positions()`, `get_balance()` — account
- `name`, `connected` — status properties

### Task 2: Create shared domain types for exchange module

**File:** `polymind/core/types.py` (or inline in exchange.py)

Types: `MarketInfo`, `OrderBookLevel`, `OrderBook`, `OrderResult`, `Position`

### Task 3: Create tests

**File:** `tests/core/test_exchange.py`

Test that `ExchangeAdapter` cannot be instantiated (ABC).
Test that a concrete subclass properly implements all methods.

### Task 4: Verify

- Run full test suite
- Run lint
