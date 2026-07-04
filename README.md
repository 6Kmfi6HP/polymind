# Polymind

<div align="center">

### AI-Native Market Making for Polymarket

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/6Kmfi6HP/polymind/actions/workflows/ci.yml/badge.svg)](https://github.com/6Kmfi6HP/polymind/actions/workflows/ci.yml)
[![Tests](https://github.com/6Kmfi6HP/polymind/actions/workflows/test.yml/badge.svg)](https://github.com/6Kmfi6HP/polymind/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/badge/coverage-1017%20tests-brightgreen?style=for-the-badge)]()

**Write market-making strategies in natural language. Let AI assemble, tune, and execute them.**

</div>

---

## Why Polymind?

Polymind merges **eight existing Polymarket projects** into one unified, AI-native market-making and cross-sectional factor framework. Four are market-making bots, four are factor research and backtesting frameworks. Users describe strategies in natural language; the framework assembles, tunes, and executes them from modular components.

```python
# Polymind approach — one sentence
"Run concentrated liquidity MM on this market, 200 USDC budget, 0.1 depth"

# Or factor-based:
"Cross-sectional momentum on all active markets, lookback 24h, top decile, 4h hold"
```

### Merged Projects — Market-Making Bots

| Project | Source | Key Contribution |
|---------|--------|------------------|
| probablyprofit-ai-framework | `randomness11/probablyprofit` | observe-decide-act loop, multi-LLM, risk mgmt, backtesting |
| pm-official-mm-keeper | `Polymarket/poly-market-maker` | AMM concentrated liquidity, Bands strategy |
| warproxxx-mm-bot | `warproxxx/poly-maker` | Event-driven MM, triple-layer risk, position merging |
| pm-terminal-all-in-one | `direkturcrypto/polymarket-terminal` | Maker rebate arbitrage, sniper, copy trade, ghost fill |

### Merged Projects — Factor Research & Backtesting

| Project | Source | Key Contribution |
|---------|--------|------------------|
| polymarket-cross-sectional-momentum | `recallnet/polymarket-cross-sectional-momentum` | Cross-sectional momentum pipeline, JSONL price store, paper OMS |
| Polymarket-Edge-Research | `oscarc17/Polymarket-Edge-Research` | DuckDB factor panels, walk-forward backtest, execution-aware simulation |
| prediction-market-backtesting | `evan-kolberg/prediction-market-backtesting` | NautilusTrader backtest engine, passive order modeling, slippage models |
| polymarket-quant | `chiantsii/polymarket-quant` | Orderbook state → fair value → edge extraction pipeline |

---

## Current Status

| Status | Layer | Description |
|--------|-------|-------------|
| ✅ **Complete** | **Core** | agent loop, config, intents, fills, ledger, portfolio, risk gates, workflows |
| ✅ **Complete** | **Strategies** | AMM (pricing/sizing), Bands (pricing/sizing), Classic MM |
| ✅ **Complete** | **Workflows** | Maker Rebate, Event MM, Sniper, Copy Trade — state machines + WorkflowRunner engine |
| ✅ **Complete** | **Pair Lifecycle** | PairLifecycleManager — split/merge/redeem/sell remainder/one-sided halt |
| ✅ **Complete** | **Execution** | PaperExecutor, LiveExecutor, FillModel, OrderIdentity, OrderSerializer |
| ✅ **Complete** | **Polymarket** | CLOB client, WebSocket adapter, Data API, Contracts gateway, Signer, Metrics, PairLifecycleManager |
| ✅ **Complete** | **Reconciliation** | Fill reconciliation, balance verification, recovery manager |
| ✅ **Complete** | **Storage** | AsyncDatabase (aiosqlite), ORM models, LedgerStore, PriceStore (JSONL), DataWarehouse |
| ✅ **Complete** | **Risk** | Kelly manager, position/exposure limits, drawdown tracker, exposure manager |
| ✅ **Complete** | **Backtesting** | Engine, DataLoader, execution models (passive/taker), factor backtester, metrics |
| ✅ **Complete** | **Factors** | Pipeline, registry, filters (spread/volume/depth), execution bridge, portfolio construction |
| ✅ **Complete** | **Studio** | NL→strategy config generator, strategy optimizer |
| ✅ **Complete** | **Agents** | Base agent ABC (observe→decide→act→reflect) |
| ✅ **Complete** | **Utils** | Logging, secrets management, kill switch, preflight checks |
| ✅ **Complete** | **CI** | GitHub Actions: lint (ruff), test (pytest+coverage), security (bandit), 3.10/3.11 matrix |
| 🔜 **Next** | **Docs Site** | Comprehensive documentation site |
| 🔜 **Next** | **E2E Tests** | Full integration and end-to-end test suite |

**1,237 tests passing · 70+ architecture modules implemented · 100+ test files · 115+ source files**

---

## Quick Start

```bash
# Install from the repository root
pip install -e .

# Inspect the CLI
polymind --help

# List implemented strategies
polymind strategies

# Run status check
polymind status
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      YOUR STRATEGY                        │
│  "Cross-sectional momentum, lookback 7d, top decile, 4h" │
│  "Run maker-rebate on BTC 15m, $0.97 cap, 10 shares"     │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                      STRATEGY ENGINE                      │
│                                                          │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ NL Parser  │  │   Strategy   │  │     Factor     │  │
│  │ prompt→cfg │  │   Registry   │  │    Registry    │  │
│  └────────────┘  └──────────────┘  └────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │               STRATEGY PLUGINS                    │  │
│  │    MM: AMM · Bands · MakerRebate · Sniper       │  │
│  │    MM: EventMM · ClassicMM · CopyTrade           │  │
│  │    FACTORS: Momentum · Volatility · Volume       │  │
│  │    FACTORS: Sentiment · Composite · Hedge        │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                       CORE ENGINE                         │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌──────┐  │
│  │  Agent   │  │   Risk    │  │  Factor   │  │Order │  │
│  │  Loop    │  │  Manager  │  │ Pipeline  │  │ Mgr  │  │
│  │obs→dec→act│  │ limits/   │  │collect→   │  │fill  │  │
│  │          │  │ drawdown  │  │ score→rank│  │track │  │
│  └──────────┘  └───────────┘  └───────────┘  └──────┘  │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                    POLYMARKET LAYER                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │CLOB API  │  │WebSocket │  │Data API  │  │Smart   │  │
│  │(HTTP)    │  │(realtime)│  │(Gamma/   │  │Contracts│  │
│  │          │  │          │  │ History) │  │split/  │  │
│  │          │  │          │  │          │  │ merge  │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
polymind/
├── pyproject.toml                # Project config & dependencies
├── README.md                     # This file
├── LICENSE                       # MIT
│
├── polymind/                     # Main package (61 modules)
│   ├── core/                     # Base contracts — intents, ledger, risk, workflows
│   ├── strategies/               # Strategy policies — AMM, Bands, Classic MM, factors
│   ├── workflows/                # State machines — MakerRebate, EventMM, Sniper, CopyTrade
│   ├── execution/                # Paper executor, fill model, order identity, serializer
│   ├── factors/                  # Pipeline, registry, filters, execution bridge
│   ├── polymarket/               # CLOB, WebSocket, Data API, contracts, signer, metrics
│   ├── reconciliation/           # Fill/balance/recovery reconciliation
│   ├── agents/                   # AI provider base
│   ├── risk/                     # Limits, drawdown, exposure, Kelly sizing
│   ├── backtesting/              # Engine, data, execution models, factor BT
│   ├── studio/                   # NL generator, optimizer
│   ├── storage/                  # DB, models, price store, ledger, warehouse
│   ├── alerts/                   # Telegram notifications
│   ├── cli/                      # CLI entry point
│   └── utils/                    # Logging, secrets, kill switch, preflight
│
├── docs/                         # Architecture decisions & reference evidence
└── tests/                        # 97 test files, 1,017+ tests
```

---

## CLI

```bash
# Run strategy via natural language
polymind run "AMM market making, 100 USDC budget, depth 0.05, spread 0.02"

# List strategies
polymind strategies

# Show status and configuration
polymind status

# Setup wizard
polymind setup
```

---

## Safety Architecture

| Feature | Status | Module |
|---------|--------|--------|
| 🛑 Kill Switch | ✅ | `polymind/utils/killswitch.py` |
| ✅ Preflight Checks | ✅ | `polymind/utils/preflight.py` |
| 🔐 Secrets Management | ✅ | `polymind/utils/secrets.py` |
| 📝 Log Redaction | ✅ | `polymind/utils/logging.py` |
| 📏 Position Limits | ✅ | `polymind/risk/limits.py` |
| 📉 Drawdown Protection | ✅ | `polymind/risk/drawdown.py` |
| 🧮 Kelly Sizing | ✅ | `polymind/risk/manager.py` |
| 📊 Exposure Limits | ✅ | `polymind/risk/exposure.py` |
| 🧪 Paper Trading Ledger | ✅ | `polymind/storage/ledger.py` |
| 🔄 Reconciliation | ✅ | `polymind/reconciliation/` |

---

## Key Learnings from Reference Projects

> **Critical insight**: Factor signals can look real in midpoint-based backtests, but midpoint prices are not executable. The reference momentum strategy showed 6.19 Sharpe in backtest and then −13.6% live paper PnL because CLOB bid-ask spread consumed the edge.

Every factor strategy in Polymind must pass an **execution-reality gate**:
- CLOB bid/ask snapshots (not Gamma midpoint) for backtesting
- Spread, depth, tick size, fees, and order type modeled explicitly
- Passive limit-order or documented taker-cost execution
- Restart-safe paper OMS ledger for dry-run promotion

See [`docs/architecture.md`](docs/architecture.md) and [`docs/architecture/decisions/`](docs/architecture/decisions/) for full ADRs.

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).

Built from eight reference projects; third-party provenance tracked separately.
