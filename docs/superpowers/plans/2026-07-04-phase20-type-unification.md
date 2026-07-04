# Phase 20: Domain Type Unification — Implementation Plan

---

### Task 1: Create shared types module

**File:** `polymind/polymarket/types.py`

Extract shared types from `data_api.py`:
- `MarketDetail` (with all fields from data_api)
- `Candle` (with all fields from data_api)
- `Trade` (with all fields from data_api)
- `VolumeInfo` (with all fields from data_api)
- `OrderLevel` → rename to `OrderBookLevel` (unified name matching client.py)
- `OrderbookSnapshot` → rename to `OrderBookSnapshot` (unified name)

### Task 2: Update data_api.py

- Remove the moved type definitions
- Import from `polymind.polymarket.types`
- Keep backward compat aliases: `OrderLevel = OrderBookLevel`, `OrderbookSnapshot = OrderBookSnapshot`

### Task 3: Update client.py

- Remove `OrderBookLevel`, `OrderBookSnapshot` (already imported from types)
- Keep `MarketSummary`, `OrderResult`

### Task 4: Update __init__.py and tests

- Update import paths in `polymind/polymarket/__init__.py`
- Run full test suite

### Task 5: Verify

- Run full test suite
- Run lint
