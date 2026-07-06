> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 26: Integration Test Suite for Polymind Core Pipeline

**Status:** Design
**Date:** 2026-07-04

## Overview

An end-to-end integration test suite that exercises the full Polymind core
pipeline with real (non-mocked) components. Unlike the existing unit tests
which mock strategy/executor/risk, these tests wire together actual
implementations and verify they compose correctly.

## Scenarios

### Scenario 1: Full Pipeline — Strategy → TradingEngine → Executor

Wire a real strategy, PaperExecutor with FillModel, and TradingEngine
together. Run a single `run_tick()` and trace the data flow:

1. Register all built-in strategies via `register_builtin_strategies()`.
2. Instantiate a real strategy (AMM, Bands, ClassicMM, etc.) with default config.
3. Create a `FillModel` in TAKER mode so orders fill immediately.
4. Create a `PaperExecutor` with that FillModel.
5. Create a `TradingEngine` with the real strategy + executor.
6. Build a `MarketSnapshot` with known bid/ask/mid prices.
7. Call `run_tick(market)` and inspect the `TickResult`.
8. Verify: `orders_proposed > 0`, `orders_placed > 0`, `risk_approved == True`,
   and the PaperExecutor internal state (orders dict, positions, cash) is
   consistent.

### Scenario 2: Workflow Integration — WorkflowRunner → PairLifecycleManager

Wire a real WorkflowRunner with PairLifecycleManager and drive the maker
rebate state machine through its lifecycle:

1. Create a `WorkflowRunner` with a `PairLifecycleManager`.
2. Send a `START` command with `params={"type": "maker_rebate"}`.
3. Verify the state machine transitions from IDLE to PLACING_ORDERS.
4. Verify `list_instances()` returns the expected entry.
5. Optionally send `STOP`/`HALT` and verify the halted state.
6. Test pair lifecycle delegation (SPLIT, MERGE, REDEEM) through the runner,
   verifying they reach the PairLifecycleManager and return `success=True`.

### Scenario 3: Risk Integration — TradingEngine + RiskGate

Wire a real risk gate into the TradingEngine and verify it rejects
oversized intents:

1. Create a `LimitsManager` with a tight `PositionLimit` (e.g. `max_size=5.0`).
2. Create a `RiskGate` wrapper that uses `LimitsManager.check_position_size()`.
3. Wire it into `TradingEngine(strategy=..., executor=..., risk_manager=...)`.
4. Run a tick where the strategy produces an intent with `size > max_size`.
5. Verify `TickResult.risk_approved == False` and `error` contains the
   rejection reason.
6. Run a compliant tick and verify it passes through.

### Scenario 4: Multi-Strategy Swap — Each strategy produces valid intents

Iterate over all registered built-in strategies, swap each into the
TradingEngine, run one tick, and verify non-empty, valid intents:

1. Build a `TradingEngine` with each strategy in turn (AMM, Bands,
   ClassicMM, MakerRebate).
2. Run `run_tick()` with a suitable `MarketSnapshot`.
3. Verify `TickResult.orders_proposed > 0` for each.
4. Verify that `intent.strategy_name` matches the strategy's name.
5. Optionally verify each intent's order structure (side, price, size sanity).

## Files

- `tests/integration/test_full_pipeline.py` (Scenario 1)
- `tests/integration/test_workflow_integration.py` (Scenario 2)
- `tests/integration/test_risk_integration.py` (Scenario 3)
- `tests/integration/test_multi_strategy.py` (Scenario 4)

## Dependencies

- `pytest` and `pytest-asyncio`
- `polymind.core.engine` — TradingEngine
- `polymind.core.strategy` — BaseMMStrategy, StrategyConfig
- `polymind.core.intents` — StrategyIntent, OrderIntent, OrderSide
- `polymind.core.risk` — RiskGate, RiskContext, RiskDecision
- `polymind.execution.executor` — PaperExecutor
- `polymind.execution.fill_model` — FillModel, FillModelConfig, FillMode, MarketSnapshot
- `polymind.strategies` — get_strategy, register_builtin_strategies
- `polymind.workflows.runner` — WorkflowRunner, CommandResult
- `polymind.polymarket.pair_lifecycle` — PairLifecycleManager
- `polymind.core.workflows` — WorkflowCommand, CommandType
- `polymind.risk.limits` — LimitsManager, LimitsConfig, PositionLimit
