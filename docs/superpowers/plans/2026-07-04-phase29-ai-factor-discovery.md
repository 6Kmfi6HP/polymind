# Phase 29: AI Factor Discovery — Implementation Plan

**Date:** 2026-07-04

---

### Task 1: Create FactorDiscovery module

**File:** `polymind/studio/factor_discovery.py`

Types:
- `FactorDefinition` dataclass: name, description, lookback, scoring_fn, top_n, rebal_freq_hours, params
- `FactorCard` dataclass: definition, sharpe, sortino, max_drawdown, total_return, win_rate, total_trades, approved
- `FactorDiscoveryError` exception

Class `FactorDiscoveryAgent`:
- `__init__(self, anthropic_api_key=None, openai_api_key=None)` — lazy SDK imports
- `async discover(description: str) -> FactorDefinition` — LLM parses NL into definition
- `async backtest(definition: FactorDefinition, price_store: PriceStore) -> FactorCard` — runs FactorBacktester on historical data
- `async discover_and_backtest(description: str, price_store: PriceStore) -> FactorCard` — combined

### Task 2: Update StrategyGenerator

**File:** `polymind/studio/generator.py`

Add new matcher patterns:
- `r"\bfactor\b.*\bdiscover"` → triggers FactorDiscoveryAgent
- `r"\bmomentum\b.*\blookback"` → enhanced momentum with lookback extraction
- `r"\b(volatility|regime|sentiment|fair.value)\b"` → maps to factor templates

### Task 3: Tests

**File:** `tests/studio/test_factor_discovery.py`

Tests:
- `test_factor_definition_construction`
- `test_factor_card_defaults`
- `test_factor_discovery_agent_initialization`
- `test_discover_custom_description` (mock LLM response)
- `test_backtest_empty_store` (empty PriceStore)
- `test_factor_card_approval_thresholds`

### Task 4: Full test suite
