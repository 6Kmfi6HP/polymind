# Phase 4 Official MM Port — Bands Strategy

**Status:** Draft
**Date:** 2026-07-03
**Reference:** pm-official-mm-keeper `strategies/bands.py`, `strategies/bands_strategy.py`

## 1. Overview

Port the Bands price-margin market-making strategy from the official Polymarket
keeper. Bands places orders at escalating spreads (bands) around a target price,
with each band having its own margin. Unlike AMM's continuous ladder, Bands
uses discrete bands that are independently configured.

**Key constraint:** Pure math — produces `StrategyIntent`.

## 2. Package Layout

```
polymind/strategies/market_making/bands/
├── __init__.py
├── pricing.py       # Band spread calculation
├── sizing.py        # Per-band position sizing
└── strategy.py      # BandsStrategy (extends BaseMMStrategy)
```

## 3. Components

### 3.1 Pricing — band spread calculation

- `BandPricingConfig(bands: List[BandConfig])` where each band has a spread_pct
- `compute_band_prices(target_price, config)` → list of `(side, price, band_idx)`
- Supports linear or custom band spacing

### 3.2 Sizing — per-band sizing

- `BandSizingConfig(exposure_per_band: float)`
- Spread exposure evenly across bands, or weighted

### 3.3 Strategy — Bands strategy

- `BandsStrategy(BandPricingConfig, BandSizingConfig)` → `BaseMMStrategy`
- Cancel all stale + place updated bands per tick
- Inherits BaseMMStrategy risk_check

## 4. Test Plan

| File | Tests |
|---|---|
| `tests/strategies/market_making/bands/test_pricing.py` | Band spread configuration, overlap check, edge cases |
| `tests/strategies/market_making/bands/test_sizing.py` | Per-band size, uniform vs weighted |
| `tests/strategies/market_making/bands/test_strategy.py` | StrategyIntent output, cancel-all, balanced bands |
