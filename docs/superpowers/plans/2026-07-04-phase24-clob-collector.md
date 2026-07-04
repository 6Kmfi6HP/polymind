# Phase 24: CLOB Data Collector — Implementation Plan

**Date:** 2026-07-04

---

### Task 1: Create SnapshotCollector

**File:** `polymind/data/collector.py`

```
CollectorConfig(poll_interval=60.0, active_only=True, max_markets=50)
SnapshotCollector(api, store, config)
  async run_once() -> int   # poll + store, return count
  async run_forever()        # loop with stop support
  async stop()
```

### Task 2: Tests

**File:** `tests/data/test_collector.py`

Mock PolymarketDataAPI.get_markets/get_orderbook, verify PriceStore receives snapshots.

### Task 3: Wire + full test suite
