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

Polymarkets need liquidity. Existing market-making bots require you to hand-code complex strategies — AMM math, spread calculations, position sizing, risk management. Polymind changes that.

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
```

Polymind merges **four existing Polymarket trading projects** into one unified framework:

| Project | Source | Key Contribution |
|---------|--------|------------------|
| probablyprofit-ai-framework | AI agent framework | observe-decide-act loop, multi-LLM, risk mgmt, backtesting |
| pm-official-mm-keeper | Polymarket official | AMM concentrated liquidity strategy, Bands strategy |
| poly-maker (warproxxx) | Community | Event-driven MM, triple-layer risk, position merging |
| pm-terminal (direkturcrypto) | Community | Maker rebate arbitrage, sniper, copy trade, ghost fill detection |

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│                    YOUR STRATEGY                        │
│  "Run maker-rebate on BTC 15m, $0.97 cap, 10 shares"   │
└────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                    STRATEGY ENGINE                      │
│                                                        │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ NL Parser  │  │   Strategy   │  │  Optimizer   │  │
│  │ prompt→cfg │  │   Registry   │  │  auto-tune   │  │
│  └────────────┘  └──────────────┘  └──────────────┘  │
│                                                        │
│  ┌────────────────────────────────────────────────┐    │
│  │              STRATEGY PLUGINS                   │    │
│  │  AMM · Bands · MakerRebate · Sniper · Copy    │    │
│  │  EventMM · ClassicMM                            │    │
│  └────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                     CORE ENGINE                         │
│  ┌──────────┐  ┌───────────┐  ┌───────────────────┐  │
│  │  Agent   │  │   Risk    │  │  Order Manager    │  │
│  │  Loop    │  │  Manager  │  │  lifecycle + fill │  │
│  │obs→dec→act│  │  kelly/   │  │  tracking         │  │
│  │          │  │ stop-loss │  │                   │  │
│  └──────────┘  └───────────┘  └───────────────────┘  │
└────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                  POLYMARKET LAYER                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │CLOB API  │  │WebSocket │  │Smart Contracts  │   │
│  │(HTTP)    │  │(realtime)│  │(merge/split/     │   │
│  │          │  │          │  │ redeem)          │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
└────────────────────────────────────────────────────────┘
```

---

## 🎯 Available Strategies

| Strategy | Source | Description |
|----------|--------|-------------|
| **AMM** 📊 | Official Keeper | Simulates Uniswap V3 concentrated liquidity with CPMM-sized order ladders |
| **Bands** 🎯 | Official Keeper | Places orders in concentric price margin bands around midpoint |
| **Maker Rebate** 💰 | pm-terminal | Buys both YES+NO at combined <$1.00, merges for profit + maker rebate |
| **Event MM** ⚡ | Poly-Maker | WebSocket-driven real-time MM with stop-loss / volatility / reverse-position risk |
| **Sniper** 🎯 | pm-terminal | Deep discount GTC orders on 5-minute markets to catch panic dumps |
| **Copy Trade** 👥 | pm-terminal | Mirrors target wallet trades in real-time via WebSocket |
| **Classic MM** 🔄 | pm-terminal | Split USDC → equal Y+N, limit sell at profit target, adaptive cut-loss |

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

# Risk-on: event-driven with tight stop-loss
polymind run "Event-driven MM, aggressive sizing, stop loss at 5%, volatility threshold 150%"
```

---

## 📋 Roadmap

```
Phase · Skeleton        ▰▰▰▰▰▰▰▰░░░░  Project scaffold, CLI, core loop, CLOB client
Phase · Port Strategies ░░░░░░░░░░░░  Port all 7 strategies to unified Python interface
Phase · Unify & Test    ░░░░░░░░░░░░  Common risk layer, integration tests, WS refactor
Phase · AI Studio       ░░░░░░░░░░░░  Natural language → strategy config, auto-optimizer
Phase · Polish          ░░░░░░░░░░░░  Docs, CI, PyPI, strategy templates gallery
```

This is a **vibe-coded** project — no fixed timelines, just iterative improvement based on what's interesting and useful.

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
│   ├── strategies/         # Strategy implementations (7 strategies)
│   ├── polymarket/         # CLOB API, WebSocket, contracts
│   ├── agents/             # AI providers (Claude, GPT, Gemini)
│   ├── risk/               # Risk management
│   ├── backtesting/        # Backtest engine
│   ├── studio/             # AI strategy studio
│   ├── storage/            # Database persistence
│   ├── alerts/             # Telegram notifications
│   └── utils/              # Logging, secrets, killswitch
│
├── cli/                    # Command-line interface
├── docs/                   # Documentation
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
- [poly-maker](https://github.com/warproxxx/warproxxx-mm-bot) by warproxxx
- [pm-terminal](https://github.com/direkturcrypto/pm-terminal-all-in-one) by direkturcrypto

---

<div align="center">

**Prediction markets need liquidity. Polymind makes it智能.**

</div>
