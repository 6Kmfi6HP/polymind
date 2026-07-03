# Reference Project Evidence Summary

**Status:** Evidence index
**Date:** 2026-07-03

This file summarizes local reference-project audits. Detailed per-project notes
may be split into separate files as implementation phases begin.

| Reference project | Evidence checked | Copy | Do not copy blindly | Polymind roadmap effect |
|-------------------|------------------|------|---------------------|-------------------------|
| `probablyprofit-ai-framework` | README, `docs/architecture.md`, `probablyprofit/__init__.py`, `agent/base.py`, `agent/strategy.py`, `risk/manager.py`, storage, backtesting, config, CLI wiring | Composition-root CLI, agent loop, risk/storage/backtesting boundaries, small public facade | Hidden singleton dependencies, broad public exports before implementation, strategy objects owning storage/execution | Keep CLI as wiring layer; keep risk/storage/backtesting behind boundaries; expose only implemented modules. |
| `pm-official-mm-keeper` | README, `poly_market_maker/strategy.py`, `orderbook.py`, AMM/Bands modules, strategy docs, config JSON, invariant tests | Snapshot to expected-orders to executor split; pure AMM/Bands math; strategy invariant tests | Positional config unpacking, in-place band mutation, universal order identity based only on price/side/token, binary assumptions in shared core | Port AMM/Bands math first; executor integration second; keep binary-market assumptions scoped. |
| `warproxxx-mm-bot` | README, `main.py`, WebSocket handlers, data processing, `trading.py`, trading utils, global state, client, merger, stats/reporting | Event-driven shell, explicit merge/cooldown/risk concepts, pure quote/sizing formulas once fed by snapshots | Global mutable state, monolithic trading file, business logic inside WebSocket callbacks, file-backed cooldown in core | Build normalized event adapters, pure decision services, explicit risk states, serialized per-market command execution. |
| `pm-terminal-all-in-one` | README, config, shared client, CTF/Safe gateway, copy-trade watcher/executor/redeemer, MM fill watcher, maker rebate executor, sniper detector/executor/scheduler | Separate bounded workflows, on-chain balance verification, per-market/per-asset serialization, wallet/chain gateway | Runtime-mutated shared config, JSON state embedded in services, callback injection for circular imports, generic trader flags | Model Maker Rebate, Sniper, Copy Trade, Classic MM, and Event MM as distinct state machines with persistence and recovery ports. |
| `polymarket-cross-sectional-momentum` | README, `.env.example`, price store, scanner, runtime, backtest collect/run scripts, experiments, postmortems, kill decision | CLOB JSONL snapshot store, score/rank/select scanner, paper OMS, experiment tombstones | Midpoint fills, static cost haircuts, market-order factor execution, replay contamination, in-memory positions | Factor Engine precedes Factor Strategies; require executable-price backtest, spread/depth filters, and paper ledger before factor promotion. |
| `Polymarket-Edge-Research` | Architecture references in Polymind docs and factor-research search results | DuckDB panels, walk-forward factor research, execution-aware simulation | Treating factor panels as execution proof | Add walk-forward and execution-aware simulation requirements to Factor Engine. |
| `prediction-market-backtesting` | Architecture references in Polymind docs and factor-research search results | Passive order modeling, slippage, queue position, PMXT instrument modeling | Assuming generic backtest fills match Polymarket CLOB execution | Model passive fills, latency, queue position, spread, and partial fills before live promotion. |
| `polymarket-quant` | Architecture references in Polymind docs and factor-research search results | Orderbook state to fair value to edge pipeline, micro-price, cross-book consistency | Treating fair-value estimates as immediately executable prices | Use micro-price and cross-book features as signals only; execution remains bid/ask constrained. |

## Documentation rule

Every roadmap phase that imports logic from a reference project must state:

1. Which files or docs were used as evidence.
2. Which patterns are copied.
3. Which anti-patterns are rejected.
4. Which acceptance gate proves the copied pattern works in Polymind.
