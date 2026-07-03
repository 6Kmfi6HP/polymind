# Cross-Sectional Momentum — Reference Postmortem

**Source:** `recallnet/polymarket-cross-sectional-momentum`
**Status:** tombstoned (2026-05-12)

## Summary

Cross-sectional momentum on Polymarket was killed after 18 completed live paper
trades produced **−$12.25 on $90 deployed (−13.6%)** with an 11% hit rate,
despite a 6.19 Sharpe backtest.

## Root Cause

**CLOB execution cost exceeds signal edge.** The backtest assumed 3% round-trip
cost using Gamma *midpoint* prices. Live execution requires crossing the CLOB
bid-ask spread, which averages 2–10% of position value. The momentum signal does
not produce enough drift to overcome the spread.

## Key Numbers

| Metric | Backtest | Live Paper |
|--------|----------|------------|
| Sharpe | 6.19 | — |
| Trades | 922 | 18 |
| Hit rate | 31.8% | 11.1% |
| Net PnL | Positive | −13.6% |
| Round-trip cost assumption | 3% | 2–10% actual |

## Lessons for Polymind

1. **Midpoint prices are untradeable.** Never backtest factor strategies against
   Gamma midpoint prices — use CLOB bid/ask as reference.
2. **Factor + execution-aware bridge.** Factor strategies in Polymind must use
   executable bid/ask models or passive limit-order models with explicit queue,
   latency, partial-fill, timeout, cancel, and adverse-selection assumptions.
3. **Short holds amplify cost.** 4–6 round-trips/day at 5% cost = 20–30% daily.
4. **YES tokens are spread-heavy.** Polymarket allocates most liquidity to NO
   (where prices are near $1.00). YES books are thin.

## What Worked

- CLOB-native data pipeline (collector, price store, scanner)
- Paper trading scaffold (dedup, budget enforcement, fill tracking)
- Backtest infrastructure (`backtest-collect` / `backtest-run`)
