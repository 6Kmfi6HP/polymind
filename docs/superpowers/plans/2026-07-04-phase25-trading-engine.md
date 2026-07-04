# Phase 25: TradingEngine — Implementation Plan

**Date:** 2026-07-04

---

### Task 1: Create TradingEngine

**File:** `polymind/core/engine.py`

```
TradingEngineConfig
  strategy_name: str
  loop_interval: float = 60.0
  dry_run: bool = True

TradingEngine
  __init__(strategy, executor, runner=None, risk_manager=None, config=None)
  async run_tick(market: MarketSnapshot) -> dict
  async run_forever(market_provider: Callable) -> None
  status() -> dict
  async stop()
```

### Task 2: Tests

**File:** `tests/core/test_engine.py`

Mock strategy, executor, runner. Verify:
- run_tick calls strategy.analyze, executor.execute
- run_tick returns result dict
- status() returns current state
- run_forever loops until stop

### Task 3: Full test suite
