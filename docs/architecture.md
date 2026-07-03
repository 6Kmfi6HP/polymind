# Polymind Architecture & Roadmap

**Status:** Target architecture, not implementation status
**Date:** 2026-07-03

This document describes the target architecture and roadmap gates. It is not a
claim that all modules or strategies are implemented. Current implementation
status belongs in `README.md` and `docs/architecture/current-state.md`.

## Executive Summary

Polymind merges **eight existing Polymarket projects** into a unified AI-native
market-making and cross-sectional factor framework. Four are market-making bots,
four are factor research and backtesting frameworks. Users describe strategies
in natural language; the framework assembles, tunes, and executes them from
modular components.

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
| polymarket-cross-sectional-momentum | `recallnet/polymarket-cross-sectional-momentum` | Cross-sectional momentum pipeline, JSONL price store, paper OMS, momentum decay analysis |
| Polymarket-Edge-Research | `oscarc17/Polymarket-Edge-Research` | DuckDB factor panels, walk-forward backtest, execution-aware simulation |
| prediction-market-backtesting | `evan-kolberg/prediction-market-backtesting` | NautilusTrader backtest engine, passive order modeling, slippage models, queue position |
| polymarket-quant | `chiantsii/polymarket-quant` | Orderbook state → fair value → edge extraction, micro-price, cross-book consistency |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        USER STRATEGY                           │
│  "Run cross-sectional momentum, lookback 7d, top decile, 4h hold" │
│  "Run maker-rebate on BTC 15m, $0.97 cap, 10 shares"          │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                       STRATEGY ENGINE                          │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  NL Parser   │  │  Strategy    │  │  Factor Registry  │   │
│  │  (prompt→    │  │  Registry    │  │  (momentum/vol/   │   │
│  │   config)    │  │  (pick impl) │  │   volume/spread)  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│                          │                                    │
│                          ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                 STRATEGY PLUGINS                       │   │
│  │  ┌───────────┐ ┌─────────┐ ┌──────────┐ ┌────────┐ │   │
│  │  │   AMM     │ │  Bands  │ │MakerRbt  │ │ Sniper │ │   │
│  │  └───────────┘ └─────────┘ └──────────┘ └────────┘ │   │
│  │  ┌───────────┐ ┌─────────┐ ┌──────────┐            │   │
│  │  │ Event MM  │ │ Classic │ │ CopyTrd  │            │   │
│  │  └───────────┘ └─────────┘ └──────────┘            │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │        CROSS-SECTIONAL FACTOR STRATEGIES       │   │   │
│  │  │  Momentum · Volatility · Volume · Sentiment    │   │   │
│  │  │  Spread · Composite · Hedge                    │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      CORE ENGINE                              │
│  ┌──────────┐  ┌───────────┐  ┌────────────┐  ┌─────────┐  │
│  │  Agent   │  │   Risk    │  │   Factor   │  │  Order  │  │
│  │  Loop    │  │  Manager  │  │  Pipeline  │  │ Manager │  │
│  │(obs→dec→ │  │(kelly,    │  │(collect→   │  │(fill    │  │
│  │  act)    │  │ stop-loss)│  │ score→rank)│  │ tracking│  │
│  └──────────┘  └───────────┘  └────────────┘  └─────────┘  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      POLYMARKET LAYER                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │CLOB API  │  │WebSocket │  │Data API  │  │Smart       │ │
│  │(HTTP)    │  │(realtime)│  │(Gamma/   │  │Contracts   │ │
│  │          │  │          │  │ History) │  │(merge/     │ │
│  └──────────┘  └──────────┘  └──────────┘  │ split/     │ │
│                                              │ redeem)    │ │
│                                              └────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Cross-Sectional Factor Framework

This is the major architectural addition beyond the original market-making
projects. The factor framework ranks markets by numeric signals, then sends
selected positions through the same passive execution and reconciliation gates
used by market-making workflows. A factor signal is not considered tradable
until its execution model passes the reality gate below.

### Factor Pipeline

```
┌─────────┐   ┌──────────┐   ┌────────┐   ┌─────────┐   ┌──────────┐
│ Collect │ → │ Compute  │ → │ Rank &  │ → │ Execute │ → │ Monitor  │
│ raw data│   │ factor   │   │ Select  │   │ trades  │   │ & exit   │
│ snapshots│  │ scores   │   │ deciles │   │(entry)  │   │(time/    │
│(bid/ask/│   │          │   │         │   │         │   │ stop)    │
│ mid/vol)│   │          │   │         │   │         │   │          │
└─────────┘   └──────────┘   └────────┘   └─────────┘   └──────────┘
     │              │              │             │             │
     ▼              ▼              ▼             ▼             ▼
  JSONL store    windowed       sorted by     limit order   time-based
  (per market)   computation    score, take    placement    or signal
                                top/bottom                 based exit
                                                              │
                                                              ▼
                                                     ┌────────────┐
                                                     │  P&L       │
                                                     │  tracking  │
                                                     │  + post-   │
                                                     │  mortem    │
                                                     └────────────┘
```

### Factor Types

| Factor | Signal input | Execution/backtest source | Lookback | Use Case |
|--------|--------------|---------------------------|----------|----------|
| **Momentum** | CLOB bid/ask-derived reference price; midpoint allowed only as signal input | Executable bid/ask or passive-fill model | 4h / 24h / 7d / 21d | Trend following |
| **Volatility** | CLOB bid/ask-derived returns | Executable bid/ask or passive-fill model | 4h / 24h / 7d | Regime filter |
| **Volume** | Gamma/Data API volume plus CLOB liquidity checks | CLOB depth and spread filters | 24h | Liquidity filter |
| **Spread** | Bid-ask spread | CLOB book | Real-time | Execution cost filter |
| **Sentiment** | External social/news signal | CLOB bid/ask execution model | Varies | Contrarian/momentum |
| **Composite** | Weighted combination | Executable-price simulation | Varies | Multi-factor |

### Factor Strategy Interface

Every factor strategy implements:

```python
class BaseFactorStrategy(BaseMMStrategy):
    """A strategy that ranks markets by a factor and trades the cross-section."""

    async def collect_snapshots(self) -> List[ClobSnapshot]:
        """Fetch bid/ask/mid for all active markets."""
        ...

    async def compute_factor(self, snapshots: List[ClobSnapshot]) -> Dict[str, float]:
        """Compute factor scores from recent snapshots."""
        # e.g., momentum = (mid_now - mid_t0) / mid_t0
        ...

    async def select_portfolio(self, scores: Dict[str, float]) -> List[Selection]:
        """Rank and select top/bottom decile."""
        # sorted(scores, key=..., reverse=True)[:top_k]
        ...

    async def execute_entry(self, selections: List[Selection]) -> None:
        """Enter positions using market-making orders (limit, not market)."""
        # Key insight from reference: midpoint prices are untradeable;
        # always use limit orders to earn the spread, not pay it.
        ...

    async def manage_exits(self) -> None:
        """Time-based or signal-based exits with reversal stop."""
        ...
```

### Key Learning from Reference Implementation

The `recallnet/polymarket-cross-sectional-momentum` project demonstrated that:

1. **Momentum signal is real** — backtest on 30 markets, 183 days: Sharpe 6.19,
   t-stat 5.07, positive decile spread 5/6 months
2. **CLOB execution cost kills the edge** — 18 live paper trades at −13.6% PnL
   with 11% hit rate because round-trip spread (2–10%) exceeds the signal
3. **Midpoint prices are untradeable** — backtesting against Gamma midpoint
   prices systemically overstates returns

**Polymind's approach**: Factor strategies use passive market-making style
execution, not market orders. Entry/exit must be modeled as resting limit
orders or another documented passive-fill mechanism. Gamma midpoint and CLOB
midpoint can inform a signal, but they must never be used as assumed fill
prices. This makes factor strategies hybrid: directional factor signal with
market-making execution.

---

## Target Directory Layout

```
polymind/
│
├── pyproject.toml              # Project config
├── README.md                   # Public-facing docs
├── LICENSE                     # MIT
│
├── polymind/                   # Main package
│   ├── __init__.py
│   │
│   ├── core/                   # Core framework
│   │   ├── agent.py            # BaseAgent — observe → decide → act
│   │   ├── config.py           # Configuration management
│   │   └── strategy.py         # BaseMMStrategy + BaseFactorStrategy
│   │
│   ├── strategies/             # Strategy implementations
│   │   ├── __init__.py
│   │   │
│   │   ├── market_making/      # Market-making strategies (bid-ask)
│   │   │   ├── amm/            # Concentrated liquidity AMM (official keeper)
│   │   │   ├── bands/          # Price margin bands (official keeper)
│   │   │   ├── maker_rebate/   # Y+N<$1 arbitrage (pm-terminal)
│   │   │   ├── event_mm/       # WebSocket-driven real-time MM (warproxxx)
│   │   │   ├── sniper/         # Deep discount orders (pm-terminal)
│   │   │   ├── copy_trade/     # Mirror target wallet (pm-terminal)
│   │   │   └── classic_mm/     # Split USDC → limit sell (pm-terminal)
│   │   │
│   │   └── factors/            # Cross-sectional factor strategies
│   │       ├── momentum/       # Momentum factor (from polymarket-cross-sectional-momentum)
│   │       ├── volatility/     # Volatility factor
│   │       ├── volume/         # Volume factor
│   │       ├── sentiment/      # Sentiment factor
│   │       ├── composite/      # Multi-factor composite (from Edge-Research)
│   │       └── hedge/          # Market-neutral hedge construction
│   │
│   ├── factors/                # Factor engine (from cs-momentum + polymarket-quant)
│   │   ├── __init__.py
│   │   ├── pipeline.py         # Collect → score → rank → select
│   │   ├── registry.py         # Factor registration & composition
│   │   ├── features.py         # Micro-price, spread, depth feature library
│   │   ├── backtest.py         # Walk-forward executable-price factor backtest
│   │   └── execution.py        # Hybrid MM execution bridge
│   │
│   ├── polymarket/             # Polymarket integration adapters
│   │   ├── client.py           # CLOB SDK adapter
│   │   ├── order_manager.py    # Order lifecycle and reconciliation
│   │   ├── websocket.py        # Market/user WebSocket adapters
│   │   ├── data_api.py         # Gamma/Data API metadata and history
│   │   ├── contracts.py        # Split/merge/redeem gateway
│   │   ├── signer.py           # Transaction signing and auth
│   │   └── metrics.py          # Venue adapter metrics
│   │
│   ├── agents/                 # AI providers
│   │   ├── base.py
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── gemini.py
│   │   ├── ensemble.py
│   │   └── intelligence.py     # News/sentiment context
│   │
│   ├── risk/                   # Risk management
│   │   ├── manager.py
│   │   ├── limits.py
│   │   └── drawdown.py
│   │
│   ├── backtesting/            # Backtesting engine
│   │   ├── engine.py           # Portfolio backtest
│   │   ├── factor_bt.py        # Cross-sectional factor backtest
│   │   ├── data.py             # Data loading/replay
│   │   └── metrics.py          # Performance metrics
│   │
│   ├── studio/                 # AI strategy studio
│   │   ├── generator.py        # NL → strategy config
│   │   └── optimizer.py        # Parameter optimization
│   │
│   ├── storage/                # Persistence
│   │   ├── database.py
│   │   ├── models.py
│   │   └── price_store.py      # JSONL snapshot store (from reference)
│   │
│   ├── alerts/
│   │   └── telegram.py
│   │
│   └── utils/
│       ├── logging.py
│       ├── secrets.py
│       ├── killswitch.py
│       └── preflight.py
│
├── cli/
│   └── main.py
│
├── docs/
│   ├── architecture.md
│   ├── strategies/
│   │   ├── market_making/
│   │   └── factors/
│   └── references/
│       ├── cross-sectional-momentum-kill.md   # Reference project postmortem
│       └── factor-research-overview.md        # Other reference projects
│
├── scripts/
│   ├── collect_snapshots.py    # Factor data collection daemon
│   └── backtest_factor.py      # Factor backtest runner
│
└── tests/
```

---

## Roadmap Gates

### Phase 0: Documentation truth alignment
- Public README distinguishes implemented, planned, and research-blocked work.
- Current-state and target-state architecture docs are separated.
- Superseded specs are marked explicitly.
- Reference project docs record what to copy and what not to copy.

### Phase 1: Polymarket adapter validation
- Validate the current SDK path before strategy implementation.
- Prefer `py-clob-client-v2` / unified SDK semantics over archived clients.
- Document public, L1, L2, builder, and user-channel auth separately.
- Document asset ID vs condition ID usage for market and user WebSocket channels.
- Document heartbeat behavior and reconnect/reconciliation requirements.

### Phase 2: Architecture spine
- Strategies produce order intents or expected-order deltas.
- Executors own CLOB transport, retries, cancellations, and order state mutation.
- Wallet/chain adapters own split, merge, redeem, approvals, and on-chain balance reads.
- Risk gates sit between strategy decisions and execution.
- Storage ports cover snapshots, positions, paper ledger, dedupe sets, and recovery state.

### Phase 3: Official MM port
- Port AMM and Bands pure math first.
- Preserve snapshot to expected-orders to executor boundary.
- Carry over strategy invariant tests: ladder symmetry, band overlap checks, cancel/replace semantics.
- Keep binary complement assumptions scoped to official-keeper adapters or strategy packages.

### Phase 4: Terminal and event workflows
- Model Maker Rebate, Event MM, Sniper, Copy Trade, and Classic MM as separate bounded workflows.
- Each workflow needs a state-machine document before implementation.
- Fill detection uses WebSocket events as wake-up signals and on-chain balances as reconciliation truth.
- Per-market or per-asset serialization is required before placing/canceling live orders.

### Phase 5: Factor engine
- Build CLOB-native snapshot store before factor strategies.
- Implement executable-price backtesting before live/paper factor promotion.
- Include spread, depth, tick size, fees, latency, order type, and partial-fill assumptions.
- Persist paper fills and positions in a restart-safe ledger.
- Reject midpoint-only backtests as evidence for tradability.

### Phase 6: Factor strategies
- Momentum, volatility, volume, sentiment, composite, and hedge strategies start only after Phase 5 gates pass.
- Each factor report separates signal evidence from execution evidence.
- Each promoted factor includes paper OMS results and failure analysis.

### Phase 7: AI studio
- Natural language maps to typed strategy configuration only.
- LLM output never bypasses schema validation, risk checks, preflight checks, or strategy implementation status.
- AI factor discovery proposes research candidates; it does not directly promote live strategies.

### Phase 8: Polish
- Documentation site
- CI pipeline for docs, lint, tests, security scan, and factor regression
- PyPI release
- Strategy templates gallery
- Multi-platform research: Kalshi, Limitless venues

---

## Execution Reality Gate

Any roadmap item that claims tradable edge must show:

1. Data source: CLOB bid/ask snapshots or full order book, not Gamma midpoint alone.
2. Execution source: passive limit-order model, actual paper fills, or documented taker-cost model.
3. Cost model: spread, fees, tick size, depth, latency, and partial fills.
4. Reconciliation: user-channel events checked against on-chain balances where applicable.
5. Restart safety: fills, positions, dedupe markers, and open intents persisted outside process memory.
6. Promotion rule: backtest success alone cannot promote a strategy to live trading.

---

## Design Decisions

### Why Python for everything
Single-language stack that `pip install` covers. The eight merged projects span
Python (probablyprofit, pm-official-mm-keeper, warproxxx-mm-bot) and TypeScript
(pm-terminal, polymarket-cross-sectional-momentum, polymarket-quant). TypeScript
projects are ported to Python for a unified codebase. The core logic (CLOB
trading, factor computation, pipeline orchestration) is algorithmic — language
is a packaging detail, not a semantic constraint.

### Factor strategies use MM execution
**Critical lesson from recallnet/polymarket-cross-sectional-momentum**:
midpoint-based backtesting systematically overstates returns. CLOB bid-ask
spread (2–10%) can exceed the factor signal. Polymind factor strategies
enter/exit via **limit orders** that earn the spread, not market orders that
pay it. This makes factor strategies inherently hybrid — directional factor
signal with MM execution.

### Factor pipeline is real-time, not batch
The reference project collected snapshots on a timer and ran scoring on each
cycle. Polymind's factor pipeline runs continuously: new snapshots → update
factor scores → re-rank portfolio → adjust positions. This allows tighter
integration with the MM infrastructure.

### Fill detection: on-chain balance is truth
Borrowing from pm-terminal's approach: WebSocket events are wake-up signals,
CLOB API is cross-check, but on-chain ERC-1155 `balanceOf` via RPC is the
source of truth for fill confirmation.

---

## Reference Project Learnings

The reference projects are evidence sources, not codebases to merge blindly.
Each one contributes either a pattern to copy, a failure mode to avoid, or both.

| Project | Copy | Do not copy blindly |
|---------|------|---------------------|
| `probablyprofit-ai-framework` | Composition-root CLI, agent loop, risk/storage/backtesting boundaries | Hidden singleton dependencies or over-broad public facade |
| `pm-official-mm-keeper` | Snapshot to expected-orders to executor split; AMM/Bands invariants | Positional config unpacking or universal order identity based only on price/side/token |
| `warproxxx-mm-bot` | Event-driven shell, explicit merge/cooldown/risk concepts | Global mutable state, monolithic `trading.py`, business logic in WebSocket callbacks |
| `pm-terminal-all-in-one` | Workflow-specific state machines, ghost-fill recovery, on-chain reconciliation | Shared mutable config and JSON state embedded in services |
| `polymarket-cross-sectional-momentum` | CLOB snapshot store, scanner shape, paper scaffold, postmortem discipline | Midpoint-only backtests, market-order factor execution, static cost haircuts |

Detailed evidence belongs in `docs/references/`.

### `recallnet/polymarket-cross-sectional-momentum`

| Aspect | Finding | Polymind Response |
|--------|---------|------------------|
| Momentum signal | Real (6.19 Sharpe backtest) | Implement momentum factor with multiple lookbacks |
| Execution cost | 2–10% spread kills edge | Factor strategies use **limit orders** (earn spread, not pay it) |
| Midpoint prices | Untradeable reference price | Backtest against CLOB bid/ask only; never Gamma midpoint |
| Hold period | Short holds amplify cost | Hold periods configurable per factor (1h–21d) |
| CLOB data pipeline | Collector + JSONL store worked correctly | Reuse `collect → appendSnapshot → readSnapshots` pattern |
| Data pipeline design | Collect mid/bid/ask per token as JSONL | Adopt the same JSONL snapshot store in `storage/price_store.py` |
| Paper trading scaffold | Dedup, budget enforcement, fill tracking | Integrate into backtesting engine |
| **−13.6% live PnL** | **18 trades, 11% hit rate** | **Hybrid factor-MM: directional signal + market-making execution** |

### `oscarc17/Polymarket-Edge-Research`

| Aspect | Insight | Polymind Response |
|--------|---------|------------------|
| DuckDB panels | Structured factor research data model | Adopt for large-scale factor analysis |
| Walk-forward backtest | Prevents overfitting in factor selection | `backtesting/factor_bt.py` with walk-forward support |
| Execution-aware simulation | Model slippage and spread, not midpoint | Execution model that uses CLOB bid/ask |
| Time-series feature panels | Structured feature engineering for factors | Factor computation pipeline with windowed features |
| Gamma/CLOB/Data API integration | Multiple data source ingestion | Unified data layer in `polymarket/data_api.py` |

### `evan-kolberg/prediction-market-backtesting`

| Aspect | Insight | Polymind Response |
|--------|---------|------------------|
| NautilusTrader integration | Professional-grade backtesting engine | Adapter layer in `backtesting/engine.py` |
| Passive order modeling | Queue position, fill probability, latency | Order execution model for limit orders |
| Slippage models | Realistic cost estimation | Backtest metrics with configurable slippage |
| Multi-market runner | Portfolio-level backtesting | Factor strategy portfolio backtest |
| PMXT custom instruments | Polymarket-specific instrument definition | Token-aware order management |

### `chiantsii/polymarket-quant`

| Aspect | Insight | Polymind Response |
|--------|---------|------------------|
| State → fair value → edge | Structured feature extraction from orderbook | Factor construction methodology |
| Micro-price | Better reference price than midpoint | Use as alternative to simple mid in factor computation |
| Cross-book consistency | Detect anomalous pricing across related markets | Composite factor with cross-market validation |
| Quote/spread/micro-price features | Rich feature set for alpha research | Factor feature library |

---

## Future Considerations

- **Multi-platform**: Kalshi, Limitless, Metaculus (factor frameworks are
  venue-agnostic; only the data source changes)
- **Plugin system**: Third-party factors as pip-installable packages
- **Web dashboard**: Factor P&L decomposition, decile spread visualization
- **Auto-factor discovery**: ML/LLM proposes factor definitions, backtests
  them, reports IC and Sharpe
