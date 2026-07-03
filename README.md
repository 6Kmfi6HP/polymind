# 🧠 Polymind

<div align="center">

### AI-Native Market Making for Polymarket

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![GitHub](https://img.shields.io/badge/GitHub-polymind-181717?style=for-the-badge&logo=github)](https://github.com/)

**Write market-making strategies in natural language. Let AI assemble, tune, and execute them.**

</div>

---

## 🔥 Why Polymind?

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

## 🏗️ Architecture

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

## 🎯 Available Strategies

### Market Making (Bid-Ask)

| Strategy | Source | Description |
|----------|--------|-------------|
| **AMM** 📊 | Official Keeper | Simulates Uniswap V3 concentrated liquidity with CPMM-sized order ladders |
| **Bands** 🎯 | Official Keeper | Places orders in concentric price margin bands around midpoint |
| **Maker Rebate** 💰 | pm-terminal | Buys both YES+NO at combined <$1.00, merges for profit + maker rebate |
| **Event MM** ⚡ | Poly-Maker | WebSocket-driven real-time MM with stop-loss / volatility / reverse-position risk |
| **Sniper** 🎯 | pm-terminal | Deep discount GTC orders on 5-minute markets to catch panic dumps |
| **Copy Trade** 👥 | pm-terminal | Mirrors target wallet trades in real-time via WebSocket |
| **Classic MM** 🔄 | pm-terminal | Split USDC → equal Y+N, limit sell at profit target, adaptive cut-loss |

### Cross-Sectional Factor (Signal-Driven)

| Strategy | Source | Description |
|----------|--------|-------------|
| **Momentum** 📈 | polymarket-cs-momentum | Rank all markets by trailing price change, long top decile, hold and exit |
| **Volatility** 🌊 | polymarket-cs-momentum | Trade volatility regimes — go short when vol spikes, long when vol compresses |
| **Volume** 💧 | polymarket-cs-momentum | Focus on liquidity-driven signals, avoid illiquid markets |
| **Sentiment** 🗣️ | polymarket-cs-momentum | Social media / news sentiment as cross-sectional ranking signal |
| **Composite** 🧬 | polymarket-cs-momentum | Multi-factor weighted composite (momentum + volume + sentiment) |
| **Hedge** 🛡️ | polymarket-cs-momentum | Long top decile, short bottom decile — market-neutral |

> **Critical insight from reference research**: Factor signals are real (6.19 Sharpe
> backtested momentum), but **midpoint prices are untradeable**. CLOB bid-ask spread
> (2–10%) can exceed the factor signal. Polymind factor strategies use
> **market-making execution** — enter/exit via limit orders that earn the spread,
> not market orders that pay it. Hybrid factor-MM. See [`docs/architecture.md`](docs/architecture.md).

---

## 🚀 Quick Start

```bash
# Install
pip install polymind

# AI-powered — describe your strategy in English
polymind run "Maker rebate on BTC 15-min options, 5 shares per side, total cap 0.97"

# Or use a pre-built strategy by name
polymind run --strategy amm --market <condition-id> --config config.yaml

# List available strategies
polymind strategies

# Paper trade (virtual portfolio)
polymind run --strategy bands --paper --capital 10000

# Full docs
polymind --help
```

### One-liner examples

```bash
# Conservative: AMM with 100 USDC budget
polymind run "AMM market making, 100 USDC budget, depth 0.05, spread 0.02"

# Aggressive: snipe panic dumps
polymind run "Snipe BTC 5-min options, max 20 shares total, 3 tiers"

# Arbitrage: maker rebate
polymind run "Maker rebate on ETH 15m, 10 shares, combined cap 0.96"

# Copy trade
polymind run --copy-trader 0x1234...abcd --sizing 0.1

# Factor: cross-sectional momentum
polymind run "Cross-sectional momentum on all markets, lookback 24h, top decile by volume"

# Factor: multi-factor composite
polymind run "Composite factor: momentum 0.5 + volume 0.3 + sentiment 0.2, top 10 markets"

# Factor: market-neutral hedge
polymind run "Factor hedge, long top decile short bottom decile, equal weight 10 each"

# Risk-on: event-driven with tight stop-loss
polymind run "Event-driven MM, aggressive sizing, stop loss at 5%, volatility threshold 150%"
```

---

## 📋 Roadmap

```
Phase · Skeleton          ▰▰▰▰▰▰▰▰░░░░  Project scaffold, CLI, core loop, CLOB client
Phase · Port MM           ░░░░░░░░░░░░  Port 7 MM strategies to unified Python interface
Phase · Factor Engine     ░░░░░░░░░░░░  Snapshot collector, factor computation, ranking pipeline
Phase · Factor Strategies ░░░░░░░░░░░░  Momentum, volatility, volume, sentiment, composite, hedge
Phase · Unify & Test      ░░░░░░░░░░░░  Common risk layer, integration tests, WS refactor
Phase · AI Studio         ░░░░░░░░░░░░  NL → strategy config, factor discovery, auto-optimizer
Phase · Polish            ░░░░░░░░░░░░  Docs, CI, PyPI, strategy templates gallery
```

This is a **vibe-coded** project — no fixed timelines, just iterative improvement based on what's interesting and useful.

### What's been learned so far

The reference project (`recallnet/polymarket-cross-sectional-momentum`) taught us
a critical lesson that shapes everything: **midpoint prices are not tradeable.**
A backtested 6.19 Sharpe momentum signal turned into −13.6% live PnL because
CLOB bid-ask spread (2–10%) consumed the entire edge. Polymind's answer: factor
strategies use **market-making execution** — enter via limit orders, earn the
spread, never pay it. Factor signal + MM execution = hybrid alpha.

---

## 📦 Project Structure

```
polymind/
├── pyproject.toml          # Project config & dependencies
├── README.md               # This file
├── LICENSE                 # MIT
│
├── polymind/               # Main package
│   ├── core/               # Agent loop, config, strategy base class
│   ├── strategies/         # Strategy implementations
│   │   ├── market_making/  # MM strategies (7 types)
│   │   └── factors/        # Factor strategies (6 types)
│   ├── factors/            # Factor engine (pipeline, registry, backtest)
│   ├── polymarket/         # CLOB API, WebSocket, Gamma API, contracts
│   ├── agents/             # AI providers (Claude, GPT, Gemini)
│   ├── risk/               # Risk management
│   ├── backtesting/        # Backtest engine (portfolio + factor)
│   ├── studio/             # AI strategy studio
│   ├── storage/            # Database + price snapshot store
│   ├── alerts/             # Telegram notifications
│   └── utils/              # Logging, secrets, killswitch
│
├── cli/                    # Command-line interface
├── docs/                   # Documentation + reference project learnings
└── tests/                  # Tests
```

---

## 🛡️ Safety First

Polymind inherits probablyprofit's safety engineering:

- **Kill Switch** — Emergency stop via file, signal (USR1), or HTTP API
- **Preflight Checks** — Validates API keys, wallet, database before trading
- **Live Confirmation** — `--confirm-live` flag + interactive "YES" required for real money
- **Log Redaction** — API keys, private keys, and secrets are never written to logs
- **Secure Credentials** — Encryption via keyring/cryptography, no plaintext storage
- **Paper Trading** — Full simulation mode with virtual portfolio
- **Position Limits** — Max exposure, daily loss, Kelly criterion sizing

---

## 🤝 Contributing

Contributions are welcome! This project is built from merging four community projects — the spirit is collaborative.

- **Report bugs**: Open a GitHub Issue
- **Submit strategies**: PR with a new strategy plugin
- **Improve docs**: PRs welcome for docs, examples, and tutorials

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📜 License

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
