# Phase 24: CLOB Data Collector — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

A CLOB snapshot collector that polls the Polymarket Data API for order-book
snapshots and stores them in the JSONL PriceStore. This is the data foundation
for Phase 6 (factor data and research engine).

## Existing components

- `polymind/storage/price_store.py` — PriceStore, PriceSnapshot (JSONL-backed)
- `polymind/polymarket/data_api.py` — PolymarketDataAPI.get_orderbook(market_id) -> OrderBookSnapshot
- `polymind/polymarket/data_api.py` — PolymarketDataAPI.get_markets() -> list[MarketDetail]

## Design

### SnapshotCollector

```python
@dataclass
class CollectorConfig:
    poll_interval: float = 60.0     # seconds between polls
    active_only: bool = True        # only poll active markets
    max_markets: int = 50           # max markets per poll cycle

class SnapshotCollector:
    def __init__(self, api: PolymarketDataAPI, store: PriceStore, config=None)

    async def run_once() -> int  # poll all markets, store snapshots, return count
    async def run_forever()      # run_once in a loop with poll_interval
    async def stop()             # stop the loop
```

### Flow

1. Fetch active markets via `api.get_markets(active=True)`
2. For each market, call `api.get_orderbook(market_id)`
3. Convert OrderBookSnapshot -> PriceSnapshot
4. Store via `store.append_snapshot()`
5. Sleep for poll_interval

## Files

- `polymind/data/collector.py`
- `tests/data/test_collector.py`
