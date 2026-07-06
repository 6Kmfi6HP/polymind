# Reference Port State

> 循环开发的状态真值源。每轮只改本文件 + 实现代码 + 测试 + 必要文档。

## Loop Info
- Last run: 2026-07-06
- Pattern: reference-port-loop
- Active reference: probablyprofit-ai-framework
- Attempt: 1/3

## Reference Project Backlog

| # | Reference (README) | Polymind target | Evidence doc | Status | Next action |
|---|-------------------|-----------------|--------------|--------|-------------|
| 1 | probablyprofit-ai-framework | agent loop, CLI wiring, risk boundaries | docs/references/probablyprofit.md | partial | AgentMemory + tests done. Remaining: position dedup in observe(), strategy filter market selection, auto-sizing via risk_manager |
| 2 | pm-official-mm-keeper | AMM/Bands parity, invariant tests | docs/references/official-mm-keeper.md | done | Parity test harness created (35 tests, all pass) |
| 3 | warproxxx-mm-bot | event shell, pure decision services | docs/references/warproxxx-mm-bot.md | partial | Verify no business logic in WebSocket callbacks; per-market serialization |
| 4 | pm-terminal-all-in-one | workflow state machines, on-chain reconcile | docs/references/pm-terminal.md | partial | Ghost-fill recovery + persistence ports vs reference |
| 5 | polymarket-cross-sectional-momentum | JSONL store, scanner, paper OMS | docs/references/cross-sectional-momentum-kill.md | partial | Paper OMS dedup/budget enforcement vs reference |
| 6 | Polymarket-Edge-Research | DuckDB panels, walk-forward | docs/references/factor-research-overview.md | partial | Walk-forward gate completeness in factor_bt |
| 7 | prediction-market-backtesting | passive fill model, queue/slippage | docs/references/factor-research-overview.md | partial | Queue position + partial-fill model coverage |
| 8 | polymarket-quant | micro-price, fair-value signals | docs/references/factor-research-overview.md | partial | Enforce micro-price as signal-only (not fill price) with tests |

Status: `not_started` | `in_progress` | `partial` | `done` | `blocked`

## Active Work Item
- ID: REF-001
- Reference: probablyprofit-ai-framework (`randomness11/probablyprofit`)
- README contribution: observe-decide-act loop, multi-LLM, risk mgmt, backtesting
- Pattern to copy: AgentMemory (bounded deque + asyncio.Lock + optional persistence); observe() records to memory; act() records to memory
- Anti-patterns rejected: hidden singleton dependencies, over-broad public exports, blurring market selection/prompt/execution/storage
- Polymind target: `polymind/core/agent.py`, `tests/core/test_agent.py`
- Acceptance gate: AgentMemory class with bounded deque + thread-safe adds + get_recent_history; BaseAgent wires memory (observe→add_observation, act→add_decision); full test coverage
- Status: **done** — AgentMemory implemented with 100-entry bounded deque, asyncio.Lock thread safety, add_observation/add_decision/get_recent_history. BaseAgent wires memory into observe() and act(). 12 new tests cover add, bounded eviction, concurrent safety, history formatting, and full-loop recording.
- Files touched: `polymind/core/agent.py` (+~50 lines AgentMemory class + 4 lines wiring), `tests/core/test_agent.py` (+12 test methods)

## Active Work Item (next)
- ID: REF-001b
- Reference: probablyprofit-ai-framework
- Next gate: Position dedup tracking (_open_positions set, _has_position, _record_position) — see probablyprofit/agent/base.py:337-345
- Status: not_started

## Gaps Queue
1. REF-001b: probablyprofit position dedup tracking (medium)
2. REF-004: pm-terminal ghost-fill recovery (medium)
3. REF-005: cross-sectional-momentum paper OMS parity (medium)

## Human Inbox
- Empty.

## Run History
| Timestamp | Reference | Item | Outcome | Tests |
|-----------|-----------|------|---------|-------|
| 2026-07-06 | probablyprofit-ai-framework | REF-001 | done | 24/24 agent tests pass (12 new AgentMemory + 12 existing BaseAgent); 1836 full suite pass, 0 regressions |
| 2026-07-06 | pm-official-mm-keeper | REF-002 | done | 35/35 parity tests pass (49 existing + 35 new = 84 total strategies/MM), 2 structural bridge skipped |
