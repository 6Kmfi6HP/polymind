请审查 Polymind 项目的架构设计和路线图，检查设计是否合理、有没有遗漏或矛盾。

## 项目背景

Polymind 是一个 AI 原生的 Polymarket 做市 + 截面因子交易框架。用户用自然语言描述策略，AI 从模块化组件中组装、调优并执行。

它合并了 **8 个现有 Polymarket 开源项目**，都在本地 `/home/debian/pmdata/` 下：

### 做市机器人（源码合并到 strategies/market_making/）

| 项目 | 本地路径 | 语言 | 提供 |
|------|---------|------|------|
| probablyprofit-ai-framework | `~/pmdata/probablyprofit-ai-framework/` | Python | AI 代理循环、多 LLM、风控、回测 |
| pm-official-mm-keeper | `~/pmdata/pm-official-mm-keeper/` | Python | AMM 集中流动性策略、Bands 策略 |
| warproxxx-mm-bot | `~/pmdata/warproxxx-mm-bot/` | Python | WebSocket 事件驱动做市、三层风控 |
| pm-terminal-all-in-one | `~/pmdata/pm-terminal-all-in-one/` | Node.js | 做市返佣、狙击、跟单、幽灵成交检测 |

### 因子研究与回测（源码合并到 factors/ + backtesting/）

| 项目 | 本地路径 | 语言 | 提供 |
|------|---------|------|------|
| polymarket-cross-sectional-momentum | `~/pmdata/polymarket-cross-sectional-momentum/` | TypeScript | 截面动量管道（collect→score→rank→execute）、JSONL 存储、纸交易 |
| Polymarket-Edge-Research | `~/pmdata/Polymarket-Edge-Research/` | Python | DuckDB 因子面板、walk-forward 回测、执行感知仿真 |
| prediction-market-backtesting | `~/pmdata/prediction-market-backtesting/` | Python | NautilusTrader 回测引擎、被动订单建模、滑点模型 |
| polymarket-quant | `~/pmdata/polymarket-quant/` | Python | 订单簿状态 → 公允价 → Alpha 提取管线 |

## 项目结构

```
polymind/                    # ~/pmdata/polymind/
├── polymind/
│   ├── core/                # 代理循环、配置、策略基类
│   ├── strategies/
│   │   ├── market_making/   # 7 种做市策略
│   │   │   ├── amm/       # 来自 pm-official-mm-keeper
│   │   │   ├── bands/     # 来自 pm-official-mm-keeper
│   │   │   ├── maker_rebate/  # 来自 pm-terminal
│   │   │   ├── event_mm/     # 来自 warproxxx-mm-bot
│   │   │   ├── sniper/       # 来自 pm-terminal
│   │   │   ├── copy_trade/   # 来自 pm-terminal
│   │   │   └── classic_mm/   # 来自 pm-terminal
│   │   └── factors/       # 6 种因子策略
│   │       ├── momentum/  # 来自 polymarket-cross-sectional-momentum
│   │       ├── volatility/
│   │       ├── volume/
│   │       ├── sentiment/
│   │       ├── composite/ # 来自 Edge-Research
│   │       └── hedge/
│   ├── factors/           # 因子引擎（管道+注册表+特征库）
│   ├── polymarket/        # CLOB API + WebSocket + Gamma API + 合约
│   ├── agents/            # AI 提供者（Claude/GPT/Gemini/集成）
│   ├── risk/              # 风控
│   ├── backtesting/       # 回测引擎（NautilusTrader + walk-forward）
│   ├── studio/            # AI 策略工作室（自然语言→配置）
│   ├── storage/           # 数据库 + JSONL 快照存储
│   ├── alerts/            # Telegram 通知
│   └── utils/             # 日志、密钥、紧急停止、预检查
├── cli/                   # 命令行入口
└── docs/
    └── architecture.md    # 完整架构文档 + 路线图
```

## 审查任务

请阅读 `~/pmdata/polymind/docs/architecture.md` 完整的架构文档，然后评估以下方面：

### 1. 整体架构合理性
- 8 个项目的合并方式是否合理？有没有更好的组织方式？
- Python 统一栈 vs 保留 TypeScript 部分，决策是否有问题？
- 目录结构是否有重叠或缺失？

### 2. 做市策略部分
- 7 种做市策略之间是否有功能重叠？哪些可以合并？
- AMM 和 Bands 策略是否应该共存，还是其中一个是另一个的子集？
- 做市策略的接口设计`BaseMMStrategy` 是否合理？

### 3. 因子策略部分
- 截面因子管道（collect→score→rank→select→execute）是否完整？
- 6 种因子策略（momentum/vol/volume/sentiment/composite/hedge）是否合理？还需要什么？
- 关键教训："midpoint prices are untradeable"——因子策略用限价单入场这个决策是否正确？还有没有更好的方案？

### 4. 路线图
- 路线图的 7 个阶段顺序是否合理？
- 有没有遗漏的关键里程碑？
- 并行依赖关系有没有问题？（比如 Factor Engine 是否需要 Port MM 完成后才能开始？）

### 5. 风险评估
- 最大的技术风险是什么？
- 最大的产品/市场风险是什么？
- 有什么是在路线图中没有体现但应该关注的？

### 6. 对比原始项目
- 与 8 个原始项目相比，Polymind 的架构是否确实提供了增量价值？
- 有没有任何原始项目中的功能在 Polymind 中被遗漏了？

请给出 1-3 个具体改进建议，并按优先级排序。
