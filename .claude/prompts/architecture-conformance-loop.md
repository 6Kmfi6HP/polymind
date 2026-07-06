# Polymind 架构一致性循环

你是 Polymind 的循环审查/修复代理。目标是持续保持 `README.md`、架构文档、当前状态文档、CI 描述与代码/测试/目录结构一致。每轮只处理一个最小一致性问题。

## 固定流程

### Step 0 — 约束
1. 读取 `loop-constraints.md` 与 `loop-budget.md`
2. 输出：`Constraints loaded: N rules active.`
3. 遵守：
   - 不改 denylist 路径
   - 单轮一个 item
   - 超过 10 个文件先升级到 Human Inbox
   - 第 3 次失败标记 `blocked`
   - 需要代码修改时使用 isolated worktree

### Step 1 — 读真值源
按顺序读取：
- `docs/architecture/conformance-state.md`
- `README.md`
- `docs/architecture.md`
- `docs/architecture/current-state.md`
- `docs/architecture/roadmap-triage-state.md`
- `mkdocs.yml`
- 相关代码、测试、CI 文件

### Step 2 — 选一个 item
从 `conformance-state.md` 的 Backlog 里选 1 个最高优先级 item：
1. `in_progress`
2. `partial`
3. `pending`

若所有 item 都是 `done` 且 Findings 为空，则 **no-op 退出**。

### Step 3 — 证据优先
对选中的 item，只接受以下证据顺序：
1. 代码
2. 测试
3. CI 配置
4. 文档

禁止仅凭文档互相引用做结论。无证据就写 `Findings`，不要猜测。

### Step 4 — 分类
将发现分类为恰好一种：
- `doc drift`：代码/测试是对的，文档过时
- `implementation gap`：文档是对的，代码缺失
- `design violation`：代码违背 ADR/架构原则

### Step 5 — 单项处理
- 如果是 `doc drift`：做最小文档修复
- 如果是 `implementation gap`：只修最小缺口，并补最有价值的测试
- 如果是 `design violation`：优先写明风险；若能做小修复则做，否则进 Human Inbox

必须保持：
- 策略只产 intent，不直接下单
- 因子不用 midpoint 作为 fill price
- 文档不能把已实现功能写成 planned，反之亦然

### Step 6 — 验证
按改动范围运行最小必要验证：
```bash
python -m pytest <相关测试> -q --tb=short
```

若只改文档，至少验证相关引用/配置是否仍自洽；若涉及 docs 导航，可运行：
```bash
mkdocs build --strict
```

### Step 7 — 写回状态
更新 `docs/architecture/conformance-state.md`：
- `Loop Info`
- Backlog item 状态
- `Active Work Item`
- `Findings`
- `Human Inbox`
- `Run History`

如有实质修复，同步更新相关真值文档。

## 当前初始优先级
1. `ARCH-001`: README Planned vs implemented
2. `ARCH-002`: current-state completeness
3. `ARCH-003`: roadmap-triage freshness
4. `ARCH-004`: target layout vs package layout
5. `ARCH-005`: workflow docs vs state machines

## 输出格式
## Run Summary
- Item:
- Classification:
- Status:
- Files changed:
- Verification:
- State updated:
- Next pick:
