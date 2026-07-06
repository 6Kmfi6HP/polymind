> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 16: PolymarketClient Real CLOB Integration — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

PolymarketClient is a stub (all methods return `[]`, `0.0`, `True`). This phase
replaces the stub with a real async wrapper around `py_clob_client.ClobClient`,
returning domain types from `polymind.polymarket.client` instead of raw SDK types.

## Architecture

```
PolymarketClient
  │
  ├── connect()     → ClobClient(host, chain_id, private_key)
  ├── get_markets() → List[MarketSummary]
  ├── get_order_book(token_id) → OrderBookSnapshot
  ├── place_order() → OrderResult
  ├── cancel_order() → bool
  └── close()       → release resources
```

## Domain Types (in polymind/polymarket/client.py)

- `MarketSummary` — market_id, condition_id, token_id, outcome, price, volume, etc.
- `OrderBookSnapshot` — bids/asks with OrderBookLevel
- `OrderResult` — order_id, status, side, price, size

## Key Design Decisions

1. **Async-first**: All public methods are async. Blocking SDK calls use `asyncio.to_thread`.
2. **No SDK types leak**: Public methods return domain types only.
3. **Error mapping**: SDK exceptions → our error hierarchy (from Phase 15).
4. **Thread safety**: `ClobClient` is not thread-safe; use a lock for concurrent access.
