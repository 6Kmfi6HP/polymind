> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 4 Official MM Port — AMM Strategy

**Status:** Draft
**Date:** 2026-07-03
**ADR:** ADR 0002 (Strategies emit intents; executors place orders)
**Reference:** pm-official-mm-keeper `strategies/amm.py`, `strategies/amm_strategy.py`

## 1. Overview

Port the AMM (Automated Market Maker) concentrated-liquidity strategy from the
official Polymarket keeper. AMM places a symmetric ladder of buy/sell limit
orders around a target price, concentrating liquidity in a configurable range.

**Key constraint:** Pure math only — no CLOB transport, no WebSocket, no SDK
calls. Produces `StrategyIntent` for the executor layer.

## 2. Package Layout

```
polymind/strategies/market_making/amm/
├── __init__.py
├── pricing.py       # Ladder price calculation (spread, tick spacing)
├── sizing.py        # Position sizing and ladder distribution
└── strategy.py      # AMMStrategy (extends BaseMMStrategy)
```

## 3. Components

### 3.1 Pricing — ladder price calculation

- `AMMPricingConfig(min_spread, max_spread, num_levels, tick_size)`
- `compute_ladder(target_price, config)` → list of `(side, price, size)` tuples
- Symmetric around target price
- Concentrated liquidity: tighter spreads near target, wider at edges

### 3.2 Sizing — position sizing

- `AMMSizingConfig(min_order_size, max_order_size, total_exposure, concentration_pct)`
- `distribute_size(total_size, levels)` → list of `(level_idx, size)`
- `concentration_pct` controls how much size goes to inner vs outer levels

### 3.3 Strategy — AMM strategy

- `AMMStrategy(AMMPricingConfig, AMMSizingConfig)` → `BaseMMStrategy`
- `analyze(market: MarketSnapshot)` → `StrategyIntent`
- Cancels all stale orders and places updated ladder on each tick

## 4. Test Plan

| File | Tests |
|---|---|
| `tests/strategies/market_making/amm/test_pricing.py` | Ladder symmetry, spread ranges, tick alignment, edge cases (zero price) |
| `tests/strategies/market_making/amm/test_sizing.py` | Size distribution, concentration, total exposure bounds |
| `tests/strategies/market_making/amm/test_strategy.py` | StrategyIntent output, cancel-all-then-place, empty input |

## 5. Future

- Bands strategy (price-margin bands, next Phase 4 step)
- Cross-market AMM (multiple outcomes from same event)
