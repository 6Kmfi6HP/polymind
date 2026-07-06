> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 20: Domain Type Unification — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

`client.py` and `data_api.py` define overlapping domain types (`OrderBookLevel` vs `OrderLevel`,
`OrderBookSnapshot` vs `OrderbookSnapshot`). This phase creates a shared `types.py` module
and resolves the split naming while maintaining backward compatibility.

## Changes

1. Create `polymind/polymarket/types.py` with canonical shared types:
   - `OrderBookLevel` (price, size, num_orders)
   - `OrderBookSnapshot` (market_id, token_id, bids, asks, timestamp, tick_size, min_order_size)
   - `MarketDetail` (market metadata)
   - `Candle`, `Trade`, `VolumeInfo`

2. `client.py` → remove duplicated types, import from types
3. `data_api.py` → remove duplicated types, import from types
4. Update `__init__.py` exports
5. Update affected tests
