# Phase 25: TradingEngine — Central Orchestrator Design

**Status:** Design
**Date:** 2026-07-04

## Overview

The **TradingEngine** is the central runtime that connects the strategy engine,
workflow runner, risk gates, and executor into a single observe-decide-act loop.

## Architecture

```
TradingEngine.run_tick():
  1. Observe — fetch market snapshots
  2. Decide — run strategy.analyze(market) → StrategyIntent
  3. Risk check — run risk gates on intent
  4. Execute — executor.execute(intent) → results
  5. Reconcile — update fills, positions, P&L
  6. Log — record the tick outcome
```

## Components

### TradingEngineConfig
- strategy_name, strategies dict
- loop_interval
- risk_limits
- dry_run flag

### TradingEngine
- Owns a strategy instance (BaseMMStrategy)
- Owns a WorkflowRunner (for lifecycle state)
- Owns an IntentExecutor
- Owns optional risk gates
- Owns a PriceStore for snapshots
- Methods: run_tick(), run_forever(), stop(), status()

### Status report
- dict with: strategy, state, positions, cash, pnl, running

## Files
- `polymind/core/engine.py`
- `tests/core/test_engine.py`
