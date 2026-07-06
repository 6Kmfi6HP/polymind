> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 31: DuckDB Research Panels — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

A DuckDB-powered replacement for the in-memory DataWarehouse, providing SQL-queryable
panels for market data, orderbook snapshots, and factor research.

## Architecture

```
DuckDBPanelStore
├── table: market_prices (market_id, timestamp, bid, ask, mid, volume)
├── table: market_metadata (market_id, question, outcome_a, outcome_b, resolution)
└── table: factor_scores (market_id, timestamp, factor_name, score)
```

### DuckDBPanelStore

```python
@dataclass
class DuckDBConfig:
    path: str = ":memory:"       # file path or :memory:
    read_only: bool = False

class DuckDBPanelStore:
    def __init__(self, config: DuckDBConfig)
    async def append_price(market_id, timestamp, bid, ask, mid, volume)
    async def query_prices(market_id, start, end) -> list[dict]
    async def get_market_list() -> list[str]
    async def compute_factors(lookback_hours) -> dict[str, float]
    async def close()
```

## Files
- `polymind/storage/duckdb_panels.py`
- `tests/storage/test_duckdb_panels.py`
