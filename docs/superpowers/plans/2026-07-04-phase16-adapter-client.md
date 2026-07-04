# Phase 16: PolymarketClient Real CLOB Integration — Implementation Plan

**Goal:** Replace PolymarketClient stub with real async wrapper around py-clob-client.

---

### Task 1: Replace client.py domain types + implementation

**File:** `polymind/polymarket/client.py` (rewrite)

Add domain types at top:
- `MarketSummary` (market_id, condition_id, token_id, outcome, price, volume_24h, liquidity, open_interest, tick_size, min_size, neg_risk, closed, created_at)
- `OrderBookLevel` (price, float, size, float, num_orders, int)
- `OrderBookSnapshot` (market_id, token_id, bids, asks, timestamp, tick_size, min_order_size)
- `OrderResult` (order_id, status, market_id, side, price, size, filled_size, remaining_size, created_at, error)

Rewrite `PolymarketClient`:
- Constructor: host, signer, chain_id, metrics
- `connect()` — instantiate ClobClient, authenticate
- `get_markets(active, limit)` → List[MarketSummary]
- `get_market(market_id)` → MarketSummary | None
- `get_order_book(token_id, depth)` → OrderBookSnapshot | None
- `get_midpoint(token_id)` → float | None
- `get_spread(token_id)` → float | None
- `get_last_trade_price(token_id)` → float | None
- `place_order(...)` → OrderResult
- `cancel_order(order_id)` → bool
- `cancel_all_orders(market_id)` → int
- `get_orders(market_id, status)` → List[OrderResult]
- `get_positions()` → List[dict]
- `get_balance()` → float
- `close()` — release

---

### Task 2: Expand client tests

**File:** `tests/polymarket/test_client.py` (rewrite)

Test (with mocks):
- connect() initializes ClobClient
- get_markets returns parsed MarketSummary list
- get_market returns MarketSummary or None
- get_order_book returns OrderBookSnapshot
- place_order requires auth, returns OrderResult
- cancel_order returns bool
- cancel_all_orders returns count
- error mapping from SDK exceptions
- close releases client

---

### Task 3: Verify

- Run full test suite
- Run lint (ruff)
