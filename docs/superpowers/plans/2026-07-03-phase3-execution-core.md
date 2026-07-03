# Phase 3 Execution Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three core execution layer components for Phase 3: OrderIdentity, FillModel, and PaperExecutor.

**Architecture:** Three modules under `polymind/execution/`, each with its own test file under `tests/execution/`. PaperExecutor implements `IntentExecutor` from `polymind.core.intents`.

**Tech Stack:** Python 3.10+, dataclasses, enums, ABCs, pytest-asyncio.

**Reference Spec:** `docs/superpowers/specs/2026-07-03-phase3-execution-core-design.md`

## Global Constraints

- Line length 100 (black/ruff config).
- `from __future__ import annotations` at top of every module.
- Timestamps use `datetime.now(timezone.utc)` via `field(default_factory=...)` in dataclasses.
- No imports from `polymind.core` modules that don't exist yet.
- Reuse existing `OrderSide`, `OrderIntent`, `StrategyIntent`, `IntentExecutor` from `polymind.core.intents`.
- Reuse `FillEvent`, `FillSource` from `polymind.core.fills`.
- Reuse `LedgerEntry`, `EntryType` from `polymind.core.ledger`.
- Every new module has a corresponding `tests/execution/test_*.py` with complete TDD coverage.
- Commit message prefix: `feat(execution): add <module>`.

---
### Task 1: OrderIdentity — stable order identity

**Files:**
- Create: `polymind/execution/__init__.py` (package marker + exports)
- Create: `polymind/execution/order_identity.py`
- Create: `tests/execution/test_order_identity.py`

**Interfaces:**
- Consumes: `OrderSide` from `polymind.core.intents`
- Produces: `OrderIdentity`

- [ ] **Step 1: Write the failing test**

- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---
### Task 2: FillModel — fill simulation assumptions

**Files:**
- Create: `polymind/execution/fill_model.py`
- Create: `tests/execution/test_fill_model.py`

**Interfaces:**
- Consumes: `OrderIntent` from `polymind.core.intents`
- Produces: `FillModel`, `FillModelConfig`, `FillResult`, `FillMode`, `MarketSnapshot`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---
### Task 3: PaperExecutor — in-memory sandbox executor

**Files:**
- Create: `polymind/execution/executor.py`
- Create: `tests/execution/test_paper_executor.py`

**Interfaces:**
- Consumes: `IntentExecutor`, `StrategyIntent`, `OrderIntent`, `CancelIntent` from `polymind.core.intents`
- Consumes: `FillEvent`, `FillSource` from `polymind.core.fills`
- Consumes: `LedgerEntry`, `EntryType` from `polymind.core.ledger`
- Consumes: `FillModel`, `MarketSnapshot` from `polymind.execution.fill_model`
- Consumes: `OrderIdentity` from `polymind.execution.order_identity`
- Produces: `PaperExecutor`, `OrderRecord`, `OrderStatus`, `PositionRecord`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---
### Task 4: Final verification

- [ ] **Step 1: Run full test suite**
- [ ] **Step 2: Verify imports work**
- [ ] **Step 3: Commit any final touch-ups**
- [ ] **Step 4: Push to origin (after human approval)**
