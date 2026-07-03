# ADR 0001: Factor execution uses executable prices

**Status:** Accepted
**Date:** 2026-07-03

## Context

The cross-sectional momentum reference showed a 6.19 Sharpe backtest and then a
−13.6% live paper result. The failure came from treating midpoint prices as if
they were executable while live trading had to pay CLOB bid-ask spreads.

Polymarket documentation exposes midpoint, spread, price, and order book APIs.
Midpoint is useful as a signal input, but it is not a fill price.

## Decision

Factor strategies may use midpoint-derived values as signal inputs, but every
backtest, paper run, and live promotion must use executable bid/ask data or a
documented passive-fill model.

Gamma midpoint or CLOB midpoint must never be used as the assumed fill price.

## Consequences

- Factor Engine work starts with CLOB snapshot storage and execution-aware
  simulation, not with strategy ranking alone.
- Backtests must model spread, depth, tick size, fees, latency, order type, and
  partial fills.
- Backtest success alone cannot promote a factor to live trading.
