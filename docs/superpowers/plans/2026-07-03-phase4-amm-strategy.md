# Phase 4 AMM Strategy Implementation Plan

**Goal:** Port the AMM concentrated-liquidity strategy from official keeper.

**Architecture:** Separate pricing/sizing/strategy modules under `polymind/strategies/market_making/amm/`.

**Tech Stack:** Python 3.10+, dataclasses, enums, pytest-asyncio.

**Reference Spec:** `docs/superpowers/specs/2026-07-03-phase4-amm-strategy.md`

## Global Constraints

- Line length 100.
- `from __future__ import annotations`.
- Reuse `OrderSide`, `OrderIntent`, `StrategyIntent`, `CancelIntent` from `polymind.core.intents`.
- Reuse `MarketSnapshot` from `polymind.execution.fill_model`.
- Every new module has corresponding test file.
- Commit prefix: `feat(strategies/amm): add ...`

---
### Task 1: AMM Pricing — ladder price calculation

- Create: `polymind/strategies/market_making/amm/pricing.py`
- Create: `tests/strategies/market_making/amm/test_pricing.py`

- [ ] TDD: write test → fail → implement → pass → commit

---
### Task 2: AMM Sizing — position sizing

- Create: `polymind/strategies/market_making/amm/sizing.py`
- Create: `tests/strategies/market_making/amm/test_sizing.py`

- [ ] TDD: write test → fail → implement → pass → commit

---
### Task 3: AMM Strategy — strategy class

- Create: `polymind/strategies/market_making/amm/strategy.py`
- Create: `tests/strategies/market_making/amm/test_strategy.py`

- [ ] TDD: write test → fail → implement → pass → commit

---
### Task 4: Final verification

- [ ] Run full test suite
- [ ] Verify imports
- [ ] Commit + push branch + draft PR
