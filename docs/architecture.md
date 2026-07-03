# Polymind Architecture & Roadmap

**Status:** Draft
**Date:** 2026-07-03

## Executive Summary

Polymind merges four existing Polymarket trading projects into a unified AI-native
market-making framework. Users describe strategies in natural language; the
framework assembles, tunes, and executes them from modular components.

### Merged Projects

| Project | Type | Language | Key Contribution |
|---------|------|----------|------------------|
| probablyprofit-ai-framework | AI agent framework | Python | observe-decide-act loop, multi-LLM, risk mgmt, backtesting |
| pm-official-mm-keeper | Official MM keeper | Python | AMM concentrated liquidity strategy, Bands strategy |
| warproxxx-mm-bot | Community MM bot | Python | Event-driven MM, triple-layer risk, position merging |
| pm-terminal-all-in-one | Trading terminal | Node.js | Maker rebate arbitrage, sniper, copy trade, ghost fill detection |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     USER STRATEGY                     │
│  "Run maker-rebate on BTC 15m, $0.97 cap, 10 shares" │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                  STRATEGY ENGINE                      │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  NL Parser   │  │  Strategy    │  │  Optimizer │ │
│  │  (prompt→    │  │  Registry    │  │  (auto-    │ │
│  │   config)    │  │  (pick impl) │  │   tune)    │ │
│  └──────────────┘  └──────────────┘  └────────────┘ │
│                          │                            │
│                          ▼                            │
│  ┌────────────────────────────────────────────────┐   │
│  │           STRATEGY PLUGINS                      │   │
│  │  ┌─────────┐ ┌────────┐ ┌─────────┐ ┌──────┐  │   │
│  │  │   AMM   │ │ Bands  │ │MakerRbt │ │Sniper│  │   │
│  │  └─────────┘ └────────┘ └─────────┘ └──────┘  │   │
│  │  ┌─────────┐ ┌────────┐ ┌─────────┐            │   │
│  │  │Event MM │ │Classic │ │CopyTrd  │            │   │
│  │  └─────────┘ └────────┘ └─────────┘            │   │
│  └────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                   CORE ENGINE                        │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐ │
│  │  Agent   │  │   Risk    │  │   Order Manager  │ │
│  │  Loop    │  │  Manager  │  │   (lifecycle)    │ │
│  │(obs→dec→ │  │(kelly,    │  │                  │ │
│  │  act)    │  │ stop-loss)│  │ fill tracking    │ │
│  └──────────┘  └───────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│               POLYMARKET LAYER                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │CLOB API  │  │WebSocket │  │Smart Contracts   │  │
│  │(HTTP)    │  │(realtime)│  │(merge/split/redeem)│ │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Directory Layout

```
polymind/
│
├── pyproject.toml              # Project config (Poetry/hatch)
├── README.md                   # Public-facing docs
├── LICENSE                     # MIT
│
├── polymind/                   # Main package
│   ├── __init__.py
│   │
│   ├── core/                   # Core framework (from probablyprofit)
│   │   ├── agent.py            # BaseAgent — observe → decide → act
│   │   ├── config.py           # Configuration management
│   │   └── strategy.py         # Strategy base class
│   │
│   ├── strategies/             # Strategy implementations
│   │   ├── __init__.py
│   │   ├── amm/                # (from pm-official-mm-keeper)
│   │   │   ├── amm.py          # CPMM concentrated liquidity math
│   │   │   └── strategy.py     # AMM strategy wrapper
│   │   ├── bands/              # (from pm-official-mm-keeper)
│   │   │   ├── bands.py        # Margin bands math
│   │   │   └── strategy.py     # Bands strategy wrapper
│   │   ├── maker_rebate/       # (from pm-terminal, ported to Python)
│   │   │   ├── detector.py     # Market discovery (slug-based)
│   │   │   ├── pricing.py      # Bid calculation + max combined cap
│   │   │   ├── executor.py     # Order placement + fill monitoring
│   │   │   ├── ghost_detect.py # Ghost fill detection & recovery
│   │   │   └── strategy.py     # Maker rebate strategy wrapper
│   │   ├── event_mm/           # (from warproxxx-mm-bot)
│   │   │   ├── pricing.py      # Order book pricing logic
│   │   │   ├── sizing.py       # Position sizing
│   │   │   ├── risk.py         # Triple-layer risk (stop/vol/reverse)
│   │   │   ├── merger.py       # Gnosis Safe position merging
│   │   │   ├── prefill.py      # Stale trade detection
│   │   │   └── strategy.py     # Event MM strategy wrapper
│   │   ├── sniper/             # (from pm-terminal, ported)
│   │   │   ├── detector.py     # 5-minute market discovery
│   │   │   ├── executor.py     # 3-tier GTC order placement
│   │   │   ├── sizing.py       # Time-based multiplier
│   │   │   └── strategy.py     # Sniper strategy wrapper
│   │   ├── copy_trade/         # (from pm-terminal, ported)
│   │   │   ├── watcher.py      # Trade detection (WS + poll)
│   │   │   ├── executor.py     # FAK buy/sell execution
│   │   │   └── strategy.py     # Copy trade strategy wrapper
│   │   └── classic_mm/         # (from pm-terminal, ported)
│   │       ├── executor.py     # Split + limit sell
│   │       ├── cut_loss.py     # Adaptive cut-loss logic
│   │       └── strategy.py     # Classic MM strategy wrapper
│   │
│   ├── polymarket/             # Polymarket integration (from probablyprofit)
│   │   ├── client.py           # CLOB API client
│   │   ├── order_manager.py    # Order lifecycle (place/cancel/fill)
│   │   ├── websocket.py        # Real-time WS data
│   │   ├── contracts.py        # Smart contract ABI + calls
│   │   └── signer.py           # Transaction signing
│   │
│   ├── agents/                 # AI providers (from probablyprofit)
│   │   ├── base.py
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── gemini.py
│   │   ├── ensemble.py
│   │   └── intelligence.py     # News/sentiment context
│   │
│   ├── risk/                   # Risk management (from probablyprofit)
│   │   ├── manager.py
│   │   ├── limits.py
│   │   └── drawdown.py
│   │
│   ├── backtesting/            # Backtesting engine (from probablyprofit)
│   │   ├── engine.py
│   │   ├── data.py
│   │   └── metrics.py
│   │
│   ├── studio/                 # AI strategy studio (new)
│   │   ├── generator.py        # NL → strategy config
│   │   └── optimizer.py        # Parameter optimization
│   │
│   ├── storage/                # Persistence (from probablyprofit)
│   │   ├── database.py
│   │   └── models.py
│   │
│   ├── alerts/                 # Notifications (from probablyprofit)
│   │   └── telegram.py
│   │
│   └── utils/                  # Utilities
│       ├── logging.py
│       ├── secrets.py
│       ├── killswitch.py
│       └── preflight.py
│
├── cli/                        # CLI (from probablyprofit)
│   └── main.py
│
├── scripts/                    # Utility scripts
├── docs/                       # Documentation
│   ├── strategies/             # Strategy docs
│   └── superpowers/specs/      # Specs
│
└── tests/                      # Tests
```

## Roadmap (Vibe-Flow)

### Phase: Skeleton
- Project scaffold: pyproject.toml, CLI entry point, README, LICENSE
- Core agent loop from probablyprofit
- Polymarket CLOB client + config
- Git init + GitHub push

### Phase: Port strategies
- AMM + Bands (Python → Python, essentially copy+refactor)
- Event MM (Python → Python, port from warproxxx)
- Maker Rebate (Node.js → Python, core pricing + merge logic)
- Sniper (Node.js → Python, order placement + sizing)
- Copy Trade (Node.js → Python, WS watcher + executor)

### Phase: Unify & test
- Common strategy interface: `observe() → decide() → act()`
- Consistent risk layer across all strategies
- Integration tests for each strategy against CLOB sandbox
- WebSocket fill detection refactor

### Phase: AI studio
- `studio/generator.py` — takes natural language, outputs strategy config
- `studio/optimizer.py` — auto-tunes spread/depth/sizing params
- Strategy explainer — AI reads on-chain performance, suggests tweaks

### Phase: Polish
- Documentation site (or comprehensive README + docs/)
- CI pipeline (lint + test + security scan)
- PyPI release
- Strategy templates gallery

## Design Decisions

### Why Python for everything
The Node.js terminal (pm-terminal) has the most sophisticated fill-detection
logic. Porting to Python is a one-time cost; the benefit is a single-language
stack that `pip install` covers, plus all strategies share the risk/agent/core
infrastructure.

### Strategy interface
Every strategy implements:
```python
class BaseMMStrategy:
    async def analyze(self, market: Market) -> StrategySignal: ...
    async def place_orders(self, signal: StrategySignal) -> List[Order]: ...
    async def manage_positions(self) -> None: ...
    async def risk_check(self) -> RiskStatus: ...
```

### Fill detection: on-chain balance is truth
Borrowing from pm-terminal's approach: WebSocket events are wake-up signals,
CLOB API is cross-check, but on-chain ERC-1155 `balanceOf` via RPC is the
source of truth for fill confirmation.

## Future Considerations

- **Multi-platform support**: Kalshi, Metaculus, PredictIt (per the original
  probablyprofit vision)
- **Plugin system**: Third-party strategies as pip-installable plugins
- **Web dashboard**: Real-time P&L, position viewer
