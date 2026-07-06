# Reference Port State

> 循环开发的状态真值源。每轮只改本文件 + 实现代码 + 测试 + 必要文档。

## Loop Info
- Last run: 2026-07-06T20:00:00Z
- Pattern: reference-port-loop
- Active reference: probablyprofit-ai-framework
- Attempt: 1/3

## Reference Project Backlog

| # | Reference (README) | Polymind target | Evidence doc | Status | Next action |
|---|-------------------|-----------------|--------------|--------|-------------|
| 1 | probablyprofit-ai-framework | agent loop, CLI wiring, risk boundaries, market filtering | docs/references/probablyprofit.md | done | REF-001 (AgentMemory) + REF-001b (position dedup) + REF-001c (auto-sizing) + REF-001d (filter_markets) all done. |
| 2 | pm-official-mm-keeper | AMM/Bands parity, invariant tests | docs/references/official-mm-keeper.md | done | Parity test harness created (35 tests, all pass) |
| 3 | warproxxx-mm-bot | event shell, pure decision services | docs/references/warproxxx-mm-bot.md | done | REF-003: Verified no business logic in WebSocket callbacks; per-market serialization via independent state machine instances. All 90 related tests pass. |
| 4 | pm-terminal-all-in-one | workflow state machines, on-chain reconcile | docs/references/pm-terminal.md | done | REF-004: ThreeWayFillVerifier ghost-fill detection complete. 23 new tests. 1872 full suite pass. |
| 5 | polymarket-cross-sectional-momentum | JSONL store, scanner, paper OMS | docs/references/cross-sectional-momentum-kill.md | done | Dedup (REF-001b) + budget enforcement (REF-005) + bid/ask cost assumptions already documented in cross-sectional-momentum-kill.md. Reference doc already states "use CLOB bid/ask as reference" clearly. |
| 6 | Polymarket-Edge-Research | DuckDB panels, walk-forward | docs/references/factor-research-overview.md | done | Walk-forward integration in FactorDiscoveryAgent.backtest() — score_series → WalkForwardResult → FactorCard.wf_* fields. 4 new tests. 393 studio/backtesting pass. |
| 7 | prediction-market-backtesting | passive fill model, queue/slippage | docs/references/factor-research-overview.md | done | REF-007: Queue position + partial-fill model integrated into FillModel._simulate_passive. 9 new tests. 1885 full suite pass. |
| 8 | polymarket-quant | micro-price, fair-value signals | docs/references/factor-research-overview.md | done | REF-008: Micro-price enforced as signal-only with 7 enforcement tests (3 fill model + 4 execution model). 388 related tests pass, 0 regressions. |

Status: `not_started` | `in_progress` | `partial` | `done` | `blocked`

## Active Work Item
- ID: REF-001d
- Reference: probablyprofit-ai-framework (`randomness11/probablyprofit`)
- README contribution: observe-decide-act loop, multi-LLM, risk mgmt, backtesting, market filtering
- Evidence doc: `docs/references/probablyprofit.md`
- Pattern to copy:
  1. `BaseStrategy.filter_markets()` as a first-class strategy interface method
  2. Default pass-through (returns all markets) for simple cases
  3. Per-strategy override for keyword, volume, active-only filtering
  4. TradingEngine.run_tick_all() — filter first, then analyze filtered markets
- Anti-patterns rejected:
  1. Hiding market selection inside analyze() where it's not composable
  2. Requiring every strategy to implement filtering from scratch
- Polymind target: `polymind/core/strategy.py` (BaseMMStrategy.filter_markets), `polymind/core/engine.py` (TradingEngine.run_tick_all), `tests/test_strategy.py`, `tests/core/test_engine.py`
- Acceptance gate: BaseMMStrategy.filter_markets exists; default returns all markets; concrete override filters correctly; TradingEngine.run_tick_all calls filter before analyze; all tests pass
- Status: **done** — filter_markets added to BaseMMStrategy with default pass-through; FilterOnlyStrategy overrides with set-based filtering; TradingEngine.run_tick_all connects filter → analyze pipeline; 5 new tests; 1922 full suite pass; 0 regressions
- Files touched: `polymind/core/strategy.py` (+10 lines), `polymind/core/engine.py` (+22 lines), `tests/test_strategy.py` (+65 lines, 5 new tests), `tests/core/test_engine.py` (+40 lines, 1 new test)

## Gaps Queue
- Empty.

## Human Inbox
- Empty.

## Run History
| Timestamp | Reference | Item | Outcome | Tests |
|-----------|-----------|------|---------|-------|
| 2026-07-06 | warproxxx-mm-bot | REF-003 | done | 90/90 tests pass (WebSocket 46 + EventMM SM 14 + Runner 30 + Strategy pending); structural verification confirms no business logic in callbacks, per-market state isolation |
| 2026-07-06 | probablyprofit-ai-framework | REF-001 | done | 24/24 agent tests pass (12 new AgentMemory + 12 existing BaseAgent); 1836 full suite pass, 0 regressions |
| 2026-07-06 | pm-official-mm-keeper | REF-002 | done | 35/35 parity tests pass (49 existing + 35 new = 84 total strategies/MM), 2 structural bridge skipped |
| 2026-07-06 | probablyprofit-ai-framework | REF-001b | done | 37/37 agent tests pass (+15 new dedup tests); 1849 full suite pass, 0 regressions |
| 2026-07-06 | pm-terminal-all-in-one | REF-004 | done | 23/23 new verifier tests pass; 84 total reconciliation tests pass; 1872 full suite pass, 0 regressions |
| 2026-07-06 | Polymarket-Edge-Research | REF-006 | done | 52/52 factor discovery tests pass (4 new walk-forward tests); 393 studio/backtesting pass; 0 regressions |
| 2026-07-06 | prediction-market-backtesting | REF-007 | done | 24/24 fill model tests pass (9 new queue+partial); 235 execution+backtesting pass; 1885 full suite pass; 0 regressions |
| 2026-07-06 | polymarket-quant | REF-008 | done | 7/7 micro-price enforcement tests pass; 388 execution/backtesting/factor tests pass; 0 regressions |
| 2026-07-06 | probablyprofit-ai-framework | REF-001c | done | 29/29 risk manager tests pass (22 new: fixed_pct, confidence_based, dynamic, stop-loss, take-profit); 337 risk/strategy/core pass; 1917 full suite pass; 0 regressions |
| 2026-07-06 | probablyprofit-ai-framework | REF-001d | done | 5/5 new filter_markets tests pass (default, custom, empty, strategy+engine integration); 1922 full suite pass; 0 regressions |
