# Polymind

<div align="center">

### AI-Native Market Making for Polymarket

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![GitHub](https://img.shields.io/badge/GitHub-polymind-181717?style=for-the-badge&logo=github)](https://github.com/)

**Write market-making strategies in natural language. Let AI assemble, tune, and execute them.**

</div>

---

## Why Polymind?

Polymarkets need liquidity. Existing trading bots require you to hand-code complex strategies — AMM math, spread calculations, position sizing, factor ranking, risk management. Polymind changes that.

**Instead of writing code, you write strategy:**

```python
# Traditional approach — hours of coding
def calculate_order_size(midpoint, balance, volatility):
    L = balance / (1/math.sqrt(midpoint) - 1/math.sqrt(midpoint + depth))
    return L * (1/math.sqrt(midpoint) - 1/math.sqrt(target_price))
```

```
# Polymind approach — one sentence
"Run concentrated liquidity MM on this market, 200 USDC budget, 0.1 depth"

# Or factor-based:
"Cross-sectional momentum on all active markets, lookback 24h, top decile, 4h hold"
```

Polymind merges **eight existing Polymarket projects** into one unified framework — four market-making bots and four factor research frameworks:

### Market-Making Bots

| Project | Source | Key Contribution |
|---------|--------|------------------|
| probablyprofit-ai-framework | `randomness11/probablyprofit` | observe-decide-act loop, multi-LLM, risk mgmt, backtesting |
| pm-official-mm-keeper | `Polymarket/poly-market-maker` | AMM concentrated liquidity, Bands strategy |
| poly-maker (warproxxx) | `warproxxx/poly-maker` | Event-driven MM, triple-layer risk, position merging |
| pm-terminal (direkturcrypto) | `direkturcrypto/polymarket-terminal` | Maker rebate, sniper, copy trade, ghost fill detection |

### Factor Research & Backtesting

| Project | Source | Key Contribution |
|---------|--------|------------------|
| polymarket-cross-sectional-momentum | `recallnet/polymarket-cross-sectional-momentum` | Cross-sectional momentum pipeline, JSONL price store, paper OMS |
| Polymarket-Edge-Research | `oscarc17/Polymarket-Edge-Research` | DuckDB factor panels, walk-forward backtest, execution-aware simulation |
| prediction-market-backtesting | `evan-kolberg/prediction-market-backtesting` | NautilusTrader backtest engine, passive order modeling, slippage models |
| polymarket-quant | `chiantsii/polymarket-quant` | Orderbook state → fair value → edge extraction pipeline |

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
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌──────┐ │
│  │  Agent   │  │   Risk    │  │  Factor   │  │Order │ │
│  │  Loop    │  │  Manager  │  │ Pipeline  │  │ Mgr  │ │
│  │obs→dec→act│  │  kelly/   │  │collect→   │  │fill  │ │
│  │          │  │ stop-loss │  │ score→rank│  │track │ │
│  └──────────┘  └───────────┘  └───────────┘  └──────┘ │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────┐
│                    POLYMARKET LAYER                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │CLOB API  │  │WebSocket │  │Gamma API │  │Smart   │ │
│  │(HTTP)    │  │(realtime)│  │(markets/ │  │Contracts│ │
│  │          │  │          │  │ history) │  │        │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## Strategy Roadmap

The strategies below are the roadmap catalog, not an implementation-status list.
Current repository state is a skeleton: package structure, CLI shell, core base
types, and reference-project research. Strategy execution backends are planned
work unless a row is explicitly marked `implemented`.

### Market Making (Bid-Ask)

| Strategy | Source | Status | Documentation contract |
|----------|--------|--------|------------------------|
| **AMM** | Official Keeper | planned port | Port pure concentrated-liquidity math first; executor integration second. |
| **Bands** | Official Keeper | planned port | Preserve snapshot to expected-orders boundary and band invariant tests. |
| **Maker Rebate** | pm-terminal | planned workflow | Dedicated state machine for paired YES/NO fills, ghost-fill recovery, merge/sell remainder. |
| **Event MM** | Poly-Maker | planned workflow | Event adapter produces normalized events; core emits order/merge/cooldown intents. |
| **Sniper** | pm-terminal | planned workflow | Dedicated scheduler/session service and token-mapping registry. |
| **Copy Trade** | pm-terminal | planned workflow | Separate ingestion, dedupe, position repository, execution, and redemption ports. |
| **Classic MM** | pm-terminal | planned workflow | Split/limit-sell logic with explicit cut-loss and reconciliation states. |

### Cross-Sectional Factor (Signal-Driven)

| Strategy | Source | Status | Documentation contract |
|----------|--------|--------|------------------------|
| **Momentum** | polymarket-cs-momentum | blocked on factor engine | Signal observed in backtest; executable edge unproven until bid/ask simulation and paper OMS pass. |
| **Volatility** | polymarket-cs-momentum | planned research | Requires CLOB snapshot store and spread/depth filters. |
| **Volume** | polymarket-cs-momentum | planned research | Liquidity filter only; not an execution signal by itself. |
| **Sentiment** | polymarket-cs-momentum | planned research | External data must remain outside the execution core. |
| **Composite** | Edge Research | planned research | Requires walk-forward factor panel and execution-aware simulation. |
| **Hedge** | polymarket-cs-momentum | planned research | Requires borrow/short/paired-position semantics to be explicit per venue. |

> **Critical insight from reference research**: Factor signals can look real in
> midpoint-based backtests, but midpoint prices are not executable. The reference
> momentum strategy showed 6.19 Sharpe in backtest and then −13.6% live paper PnL
> because CLOB bid-ask spread consumed the edge. Polymind factor strategies must
> pass an execution-reality gate: CLOB bid/ask snapshots, spread/depth filters,
> passive limit-order assumptions, and a restart-safe paper OMS ledger. See
> [`docs/architecture.md`](docs/architecture.md).

---

## Quick Start

```bash
# Install the local skeleton from the repository root
pip install -e .

# Inspect the CLI shell
polymind --help

# List roadmap strategies and their implementation status
polymind strategies
```

### Planned CLI shape

The commands below document the intended user experience. They must not be
treated as live-trading readiness until the matching strategy row is marked
`implemented` and its safety gates are documented as passing.

```bash
# Planned: conservative AMM with 100 USDC budget
polymind run "AMM market making, 100 USDC budget, depth 0.05, spread 0.02"

# Planned: maker rebate workflow
polymind run "Maker rebate on ETH 15m, 10 shares, combined cap 0.96"

# Planned: copy trade workflow
polymind run --copy-trader 0x1234...abcd --sizing 0.1

# Planned: factor momentum, blocked on executable-price factor engine
polymind run "Cross-sectional momentum on all markets, lookback 24h, top decile by volume"
```

---

## Roadmap

```text
Phase 0 · Documentation truth alignment  current   README/status/spec/reference docs match implementation reality
Phase 1 · Polymarket adapter validation  planned   SDK v2/unified SDK spike, auth-level split, WebSocket ID semantics
Phase 2 · Architecture spine             planned   strategy intent boundary, risk gate, order executor, storage ports
Phase 3 · Official MM port               planned   AMM/Bands pure math, order-delta adapter, invariant tests
Phase 4 · Terminal/Event workflows       planned   Maker rebate, sniper, copy trade, event MM state machines
Phase 5 · Factor engine                  planned   CLOB snapshot store, executable-price backtest, paper OMS ledger
Phase 6 · Factor strategies              planned   momentum, volatility, volume, composite, hedge after execution gate
Phase 7 · AI Studio                      planned   NL to typed config after strategy schemas stabilize
Phase 8 · Polish                         planned   docs site, CI, PyPI, strategy gallery
```

### Execution reality gate for factor work

Before any factor strategy is promoted from research to implementation:

- Backtests must use executable CLOB bid/ask data or a documented passive-fill model.
- Gamma midpoint or CLOB midpoint may be used as a signal input, but never as an assumed fill price.
- Spread, depth, tick size, fees, and order type must be modeled explicitly.
- FOK/FAK marketable orders are not the default for factor entry/exit.
- Paper runs must persist fills and positions in a restart-safe ledger.
- Live promotion requires reconciliation against user-channel events and on-chain balances.
---

## Project Structure

Target layout. Many packages are currently placeholders until their roadmap
phase is reached.

```text
polymind/
├── pyproject.toml          # Project config & dependencies
├── README.md               # Public-facing roadmap and status
├── LICENSE                 # MIT
│
├── polymind/               # Main package
│   ├── core/               # Agent loop, config, strategy base class
│   ├── strategies/         # Strategy implementations by bounded context
│   │   ├── market_making/  # MM strategy families
│   │   └── factors/        # Factor strategy families after factor gate
│   ├── factors/            # Factor engine: snapshots, scoring, ranking, execution bridge
│   ├── polymarket/         # CLOB, Data API, WebSocket, contracts adapters
│   ├── agents/             # AI providers
│   ├── risk/               # Limits, drawdown, sizing, kill-switch policy
│   ├── backtesting/        # Executable-price simulation and metrics
│   ├── studio/             # NL to typed strategy config
│   ├── storage/            # Database, repositories, price snapshot store, paper ledger
│   ├── alerts/             # Notifications
│   └── utils/              # Logging, secrets, preflight helpers
│
├── cli/                    # Composition root for CLI wiring
├── docs/                   # Architecture decisions and reference evidence
└── tests/                  # Contract, strategy invariant, and integration tests
```

---

## Safety Requirements

These are inherited safety requirements from the reference projects, not a claim
that every item is already implemented.

- **Kill Switch** — Emergency stop via file, signal, or API before live trading is enabled.
- **Preflight Checks** — Validate API keys, wallet, balances, allowances, database, and venue restrictions.
- **Live Confirmation** — Require explicit live-mode confirmation before real orders.
- **Log Redaction** — Never write API keys, private keys, passphrases, signatures, or full auth headers to logs.
- **Secure Credentials** — Keep private keys and CLOB API credentials outside strategy code.
- **Paper Trading** — Use a restart-safe ledger before live promotion.
- **Position Limits** — Enforce per-market, portfolio, drawdown, daily-loss, and strategy-specific limits.

---

## Contributing

Contributions are welcome. This project is built from market-making bots and factor-research references; the spirit is collaborative.

- **Report bugs**: Open a GitHub Issue
- **Submit strategies**: PR with a new strategy plugin
- **Improve docs**: PRs welcome for docs, examples, and tutorials

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Built from:
- [probablyprofit](https://github.com/randomness11/probablyprofit) by @ankitkr0
- [poly-market-maker](https://github.com/Polymarket/poly-market-maker) by Polymarket
- [poly-maker](https://github.com/warproxxx/poly-maker) by warproxxx
- [pm-terminal](https://github.com/direkturcrypto/polymarket-terminal) by direkturcrypto
- [polymarket-cross-sectional-momentum](https://github.com/recallnet/polymarket-cross-sectional-momentum) by recallnet
- [Polymarket-Edge-Research](https://github.com/oscarc17/Polymarket-Edge-Research) by oscarc17
- [prediction-market-backtesting](https://github.com/evan-kolberg/prediction-market-backtesting) by evan-kolberg
- [polymarket-quant](https://github.com/chiantsii/polymarket-quant) by chiantsii
- [polymarket-l2-collector](https://github.com/Caiooooo/polymarket-l2-collector) by Caiooooo

---

<div align="center">

**Prediction markets need liquidity. Polymind makes it智能.**

</div>
