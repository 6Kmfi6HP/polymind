# Polymind 参考项目循环移植 Loop

你是 Polymind 的循环开发代理。每一轮从状态文件恢复上下文，对照 README 描述的 8 个参考项目继续移植，做完一项验证一项，并把结果写回状态文件。

## 每轮固定顺序（不可跳过）

### Step 0 — 约束与预算
1. 读取并遵守 `loop-constraints.md`（denylist、attempt cap=3、L2 用 isolated worktree）
2. 读取 `loop-budget.md` 与 `loop-run-log.md`（若超预算 → report-only 并退出）
3. 确认开头输出：`Constraints loaded: N rules active.`

### Step 1 — 恢复状态
读取（按顺序）：
- `README.md` — Merged Projects 两张表（8 个参考项目）
- `docs/architecture/reference-port-state.md` — **本轮唯一状态真值**
- `docs/architecture.md` — 目标架构、Roadmap Gates、Execution Reality Gate
- `docs/architecture/current-state.md` — 已实现清单（避免重复造轮子）
- `docs/references/reference-projects.md` — Copy / Do not copy 索引
- 当前 Active Work Item 对应的 `docs/references/<project>.md`

### Step 2 — 选题（每轮只做一件事）
从 `reference-port-state.md` 的 Backlog 或 Gaps Queue 中选 **1 个**最高优先级条目：
1. `in_progress` 或 `partial`（有未完成 acceptance gate）
2. `not_started`，按 README 表顺序 1–8
3. 若 Backlog 全 `done` 且无 Gaps → **no-op 退出**

**禁止**一轮内跨多个参考项目或大重构。

### Step 3 — 参考项目证据链（强制）
选定后，在实现前更新 Active Work Item：
1. README 声称（Key Contribution 原文）
2. Evidence doc 路径
3. Pattern to copy（≤5 条）
4. Anti-patterns rejected
5. Polymind target 包路径
6. Acceptance gate（可验证标准）

证据不足 → 写入 Gaps Queue，标 `blocked`，不猜测。

### Step 4 — 实现前对照
搜索 `polymind/`、`tests/`、`current-state.md` 确认是否已实现。已实现则只更新状态，标 `done`。

### Step 5 — 最小实现（L2）
- 一次只做一个 acceptance gate
- 策略只产 intent，不直接调 CLOB（ADR 0002）
- 因子不用 midpoint 作 fill price（ADR 0001）
- 单轮改动 ≤10 文件；超出 → Human Inbox
- `pyproject.toml` / auth / security → Human Inbox

实现后运行：
```bash
python -m pytest <相关测试> -q --tb=short
```

### Step 6 — 验证
- 测试通过才能标 `done` 或 `partial`
- 第 3 次失败 → `blocked` + Human Inbox

### Step 7 — 更新状态
更新 `docs/architecture/reference-port-state.md`（Loop Info、Backlog、Active Work Item、Gaps、Run History）。
有实质交付时同步 `docs/architecture/current-state.md` 一行摘要。

### Step 8 — 写运行日志
追加 JSON 到 `loop-run-log.md`：
```json
{"run_id":"<ISO8601>","pattern":"reference-port-loop","reference":"<project>","item":"<id>","duration_s":0,"actions_taken":1,"escalations":0,"tokens_estimate":0,"outcome":"no-op|partial|done|blocked","tests":"<cmd>","note":"<one line>"}
```

## 8 个参考项目映射

| # | README 项目 | Polymind 落点 | 证据文档 |
|---|------------|--------------|---------|
| 1 | probablyprofit | `core/agent.py`, `cli/`, `risk/` | probablyprofit.md |
| 2 | pm-official-mm-keeper | `strategies/market_making/` | official-mm-keeper.md, official-mm-parity.md |
| 3 | warproxxx-mm-bot | `workflows/event_mm/` | warproxxx-mm-bot.md |
| 4 | pm-terminal-all-in-one | `workflows/*`, `reconciliation/` | pm-terminal.md |
| 5 | cross-sectional-momentum | `storage/price_store.py`, `factors/` | cross-sectional-momentum-kill.md |
| 6 | Polymarket-Edge-Research | `storage/warehouse.py`, `backtesting/factor_bt.py` | factor-research-overview.md |
| 7 | prediction-market-backtesting | `backtesting/execution_model.py` | factor-research-overview.md |
| 8 | polymarket-quant | `factors/features.py` | factor-research-overview.md |

## 输出格式（每轮结尾）
### Run Summary
- Reference / Item / Status / Tests / State updated / Next pick

## 硬约束
- 不 auto-merge；不猜参考行为；不一轮做多项目
- 状态以 `reference-port-state.md` 为准
