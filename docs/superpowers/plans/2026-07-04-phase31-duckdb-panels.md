# Phase 31: DuckDB Research Panels — Implementation Plan

**Date:** 2026-07-04

---

### Task 1: Create DuckDBPanelStore

**File:** `polymind/storage/duckdb_panels.py`

- DuckDBConfig dataclass
- DuckDBPanelStore class with SQL schema and async wrapper
- Tables: market_prices, market_metadata, factor_scores

### Task 2: Tests

**File:** `tests/storage/test_duckdb_panels.py`

- test_create_tables, test_append_price, test_query_prices
- test_get_market_list, test_compute_factors
- test_multiple_markets, test_empty_query

### Task 3: Full test suite
