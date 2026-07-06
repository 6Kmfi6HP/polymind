> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 29: AI Factor Discovery Engine — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

An AI-powered factor discovery engine that uses LLMs to propose, validate,
and backtest factor definitions against Polymarket CLOB data — and lets the
`StrategyGenerator` recognise factor descriptions.

## Architecture

```
NL description → FactorDiscoveryAgent → FactorDefinition → FactorBacktester → FactorCard
```

### FactorDiscoveryAgent

Uses an LLM (Anthropic/OpenAI) to parse a natural language factor description
into a structured `FactorDefinition`:

```python
@dataclass
class FactorDefinition:
    name: str
    description: str
    lookback: str          # "24h", "7d", "14d"
    scoring_fn: str        # "momentum", "volatility", "custom"
    top_n: int
    rebal_freq_hours: int
    params: dict
```

### FactorCard

Result of backtesting a `FactorDefinition`:

```python
@dataclass
class FactorCard:
    definition: FactorDefinition
    sharpe: float
    sortino: float
    max_drawdown: float
    total_return: float
    win_rate: float
    total_trades: int
    approved: bool          # meets minimum performance thresholds
```

### Generator Integration

New matcher in `StrategyGenerator` that detects factor-related NL descriptions
and maps them to `FactorDefinition` instead of just `momentum`.

## Files

- `polymind/studio/factor_discovery.py` — FactorDefinition, FactorCard, DiscoveryAgent
- `tests/studio/test_factor_discovery.py`
- Update `polymind/studio/generator.py` — add factor-specific matching
