# Factor Research Reference Overview

**Sources:**

- `/home/debian/pmdata/polymarket-cross-sectional-momentum`
- `recallnet/polymarket-cross-sectional-momentum`
- `oscarc17/Polymarket-Edge-Research`
- `evan-kolberg/prediction-market-backtesting`
- `chiantsii/polymarket-quant`

## Evidence checked for cross-sectional momentum

- `README.md:5-13,106-109`
- `executors/cross-sectional-momentum/.env.example:1-11`
- `src/store/price-store.ts:5-52`
- `src/momentum/scanner.ts:6-63,85-102`
- `src/index.ts:3-17,68-117`
- `scripts/backtest-collect.ts:19-20,33-84,95-190`
- `scripts/backtest-run.ts:71,149-239,417-469`
- `experiments/politics-21d-momentum.md:15-25,47-53,65-68,82-89`
- `docs/explanation/postmortem-cross-sectional-momentum.md:20-26,42-56,60-88,101-136`
- `docs/decision/kill-cross-sectional-momentum.md:29-35,43-55,72-77,101-117`

## Copy

- Append-only CLOB JSONL snapshot store with bid, ask, mid, token ID, and timestamp.
- Scanner shape: filter by executable book conditions, compute score, rank, select, build intents.
- Paper OMS with budget, dedupe, fill tracking, and restart-safe ledger.
- Experiment docs that tombstone failed strategies with data.
- Walk-forward and execution-aware backtesting from the broader factor references.

## Do not copy blindly

- Gamma midpoint or CLOB midpoint as assumed fill price.
- Static round-trip cost haircut as a substitute for spread/depth/queue modeling.
- Market-order entry/exit for short-hold factor strategies.
- Live snapshot stores contaminated with replay/backtest data.
- In-memory positions without persistent reconciliation.

## Polymind roadmap implication

Factor Engine precedes Factor Strategies. The engine must first establish
CLOB-native snapshots, executable-price simulation, paper OMS, and promotion
rules. Momentum and other factors remain research-blocked until those gates pass.
