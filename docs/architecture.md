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
│  │  NL Parser   │  │  Strategy    │  │  Factor/Workflow │   │
│  │  (prompt→    │  │  Registry    │  │  Registries      │   │
│  │   typed cfg) │  │  (pick impl) │  │  (signals/flows) │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│                          │                                    │
│                          ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              POLICIES AND WORKFLOWS                    │   │
│  │  Policies: AMM · Bands · Classic MM                    │   │
│  │  Workflows: Maker Rebate · Event MM · Sniper · Copy    │   │
│  │  Shared: pair lifecycle · scheduler · recovery         │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │        FACTOR / FILTER / OVERLAY STRATEGIES   │   │   │
│  │  │  Signals: Momentum · Regime · Sentiment       │   │   │
│  │  │  Filters: Spread · Depth · Volume · Fees      │   │   │
│  │  │  Overlays: Composite · Hedge · Exposure caps  │   │   │
│  │  │  Structural: Parity · Cross-market · Fair val │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      CORE ENGINE                              │
│  ┌──────────┐  ┌───────────┐  ┌────────────┐  ┌─────────┐  │
│  │  Agent   │  │   Risk    │  │   Factor   │  │Executor │  │
│  │  Loop    │  │  Gates    │  │  Engine    │  │(intent→ │  │
│  │(obs→dec→ │  │(limits,   │  │(features,  │  │ order,  │  │
│  │  act)    │  │ exposure) │  │ filters)   │  │ fills)  │  │
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

### Factor Taxonomy

Polymind separates **signals**, **tradability filters**, and **portfolio
overlays**. They are different abstractions and must not be collapsed into one
`FactorStrategy` base class.

#### Signal factors

| Signal family | Signal input | Execution/backtest source | Lookback | Use case |
|---------------|--------------|---------------------------|----------|----------|
| **Momentum** | CLOB bid/ask-derived reference price; midpoint allowed only as signal input | Executable bid/ask or passive-fill model | 4h / 24h / 7d / 21d | Trend following |
| **Volatility / regime** | CLOB bid/ask-derived returns, realized spread, event regime | Executable bid/ask or passive-fill model | 4h / 24h / 7d | Regime filter or signal conditioner |
| **Sentiment / news** | External social/news signal with timestamped provenance | CLOB bid/ask execution model | Varies | Contrarian or momentum signal |
| **Fair-value / microstructure** | Orderbook state, micro-price, depth imbalance, fair-value model | Executable bid/ask, passive-fill model, or documented taker-cost model | Real-time to event horizon | Model price versus executable price |
| **Structural / relative value** | Complement parity, cross-market consistency, resolution mechanics | Paired-leg executable simulation with hedge/bailout states | Real-time | Constraint or relative-value trades |

#### Tradability filters

| Filter | Input | Purpose |
|--------|-------|---------|
| **Volume** | Gamma/Data API volume plus CLOB liquidity checks | Liquidity and capacity filter |
| **Spread** | Bid-ask spread and tick size | Execution-cost filter |
| **Depth** | Book depth at intended price levels | Capacity and market-impact filter |
| **Fees** | Observed fee regime or conservative fallback | Expected-value filter |
| **Freshness** | Snapshot timestamp, WebSocket heartbeat, API lag | Stale-data rejection |
| **Time to resolution** | Market close / resolution metadata | Holding-period and settlement-risk filter |

#### Portfolio overlays

| Overlay | Purpose |
|---------|---------|
| **Composite** | Weighted or learned combination of signal families after each signal passes validation |
| **Hedge / exposure neutralization** | Market-neutral or category-neutral construction with explicit YES/NO and paired-position semantics |
| **Risk caps** | Per-market, per-token, per-category, per-asset, and correlated-exposure limits |

### Factor Strategy Contracts

Factor strategies do **not** inherit from `BaseMMStrategy`. They share a neutral
strategy contract and use an execution bridge when a directional factor needs
market-making-style passive execution.

```python
class BaseStrategy(ABC):
    """Framework-neutral strategy boundary."""

    async def decide(self, context: StrategyContext) -> list[StrategyIntent]:
        """Return intents or workflow commands. Never place exchange orders."""
        ...


class FactorSignalModel(ABC):
    """Computes signal scores from validated snapshots and feature panels."""

    async def compute_scores(self, universe: UniverseSnapshot) -> dict[str, float]:
        ...


class TradabilityFilter(ABC):
    """Rejects markets where the signal is not executable after costs."""

    async def filter(self, universe: UniverseSnapshot) -> TradableUniverse:
        ...


class PortfolioConstructor(ABC):
    """Converts ranked scores into desired positions under risk constraints."""

    async def construct(self, scores: dict[str, float]) -> PortfolioTarget:
        ...


class FactorExecutionBridge(ABC):
    """Converts a portfolio target into order intents for the executor."""

    async def to_order_intents(self, target: PortfolioTarget) -> list[OrderIntent]:
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

**Polymind's approach**: Factor strategies use execution-aware order intents,
not midpoint or unconditional market-order fills. Entry/exit must be modeled as
either conservative taker execution at executable bid/ask including costs, or
post-only/passive limit orders with documented queue position, latency,
partial-fill, timeout, adverse-selection, and cancel assumptions. Gamma midpoint
and CLOB midpoint can inform a signal, but they must never be used as assumed
fill prices. This makes factor strategies hybrid: directional factor signal
with an execution bridge that may use market-making mechanics.

---

## Target Directory Layout

```
polymind/
│
├── pyproject.toml              # Project config
├── README.md                   # Public-facing docs
├── LICENSE                     # Repository license; third-party provenance tracked separately
│
├── polymind/                   # Main package
│   ├── __init__.py
│   │
│   ├── core/                   # Framework contracts and dependency-inward models
│   │   ├── agent.py            # BaseAgent — observe → decide → act
│   │   ├── config.py           # Configuration management
│   │   ├── intents.py          # OrderIntent, CancelIntent, WorkflowCommand, PortfolioTarget
│   │   └── strategy.py         # BaseStrategy, MarketMakingPolicy, FactorSignalModel
│   │
│   ├── strategies/             # Pure strategy policies; no CLOB transport side effects
│   │   ├── __init__.py
│   │   │
│   │   ├── market_making/      # Bid/ask policy engines
│   │   │   ├── amm/            # Concentrated-liquidity ladder math (official keeper)
│   │   │   ├── bands/          # Price-margin band sizing math (official keeper)
│   │   │   └── classic_mm/     # Split/limit-sell policy surface
│   │   │
│   │   └── factors/            # Strategy adapters around factor engine components
│   │       ├── momentum/
│   │       ├── regime/
│   │       ├── sentiment/
│   │       ├── fair_value/
│   │       ├── structural/
│   │       └── composite/
│   │
│   ├── workflows/              # Stateful trading workflows with recovery semantics
│   │   ├── maker_rebate/       # Paired YES/NO fills, merge/redeem, one-sided halt
│   │   ├── event_mm/           # WebSocket-driven wake-up shell and cooldown flow
│   │   ├── sniper/             # Deep discount reactive bid workflow
│   │   └── copy_trade/         # Target wallet ingestion, dedupe, proportional execution
│   │
│   ├── factors/                # Factor engine and research-domain primitives
│   │   ├── __init__.py
│   │   ├── pipeline.py         # Universe → features → score → rank → target
│   │   ├── registry.py         # Signal/filter/overlay registration
│   │   ├── features.py         # Micro-price, spread, depth, imbalance, state features
│   │   ├── filters.py          # Spread, volume, depth, fee, freshness, time filters
│   │   ├── portfolio.py        # Deciles, sizing, hedging, exposure caps
│   │   └── execution.py        # FactorExecutionBridge to order intents
│   │
│   ├── execution/              # Venue-neutral execution orchestration
│   │   ├── executor.py         # Intent → exchange order lifecycle
│   │   ├── order_identity.py   # Stable identity for audit, dedupe, cancel/replace
│   │   ├── fill_model.py       # Passive/taker fill assumptions for paper/backtest
│   │   └── serializer.py       # Per-market/per-token command serialization
│   │
│   ├── reconciliation/         # Fill and balance truth model
│   │   ├── fills.py            # WebSocket wake-up + CLOB cross-check
│   │   ├── balances.py         # ERC-1155 balanceOf truth reads
│   │   └── recovery.py         # Ghost-fill, partial-fill, restart recovery
│   │
│   ├── polymarket/             # Polymarket integration adapters
│   │   ├── client.py           # CLOB SDK adapter
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
│   ├── risk/                   # Risk gates between strategy intents and execution
│   │   ├── manager.py
│   │   ├── limits.py
│   │   ├── exposure.py
│   │   └── drawdown.py
│   │
│   ├── backtesting/            # Backtesting and paper/sandbox execution
│   │   ├── engine.py           # Portfolio backtest
│   │   ├── factor_bt.py        # Cross-sectional factor backtest
│   │   ├── data.py             # Data loading/replay
│   │   ├── execution_model.py  # Queue, latency, partial-fill, fee, slippage models
│   │   └── metrics.py          # Performance, capacity, attribution metrics
│   │
│   ├── studio/                 # AI strategy studio
│   │   ├── generator.py        # NL → typed strategy config
│   │   └── optimizer.py        # Parameter optimization under promotion gates
│   │
│   ├── storage/                # Persistence ports and adapters
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── price_store.py      # Append-only CLOB snapshot store
│   │   ├── ledger.py           # Paper/live fills, positions, cash, dedupe markers
│   │   └── warehouse.py        # DuckDB-style research panels
│   │
│   ├── alerts/
│   │   └── telegram.py
│   │
│   ├── cli/
│   │   └── main.py
│   │
│   └── utils/
│       ├── logging.py
│       ├── secrets.py
│       ├── killswitch.py
│       └── preflight.py
│
├── docs/
│   ├── architecture.md
│   ├── architecture/
│   │   └── decisions/
│   ├── strategies/
│   │   ├── market_making/
│   │   └── factors/
│   └── references/
│       ├── cross-sectional-momentum-kill.md
│       └── factor-research-overview.md
│
├── scripts/
│   ├── collect_snapshots.py    # Factor data collection daemon
│   └── backtest_factor.py      # Factor backtest runner
│
└── tests/
```

---

## Roadmap Gates

The roadmap has **ten gates: Phase 0 through Phase 9**. Phase 4, Phase 5, and
Phase 6 may run in parallel after Phase 3 because they depend on the shared
contracts, adapters, execution model, and persistence spine rather than on each
other.

### Phase 0: Documentation, provenance, and license truth alignment
- Public README distinguishes implemented, planned, and research-blocked work.
- Current-state and target-state architecture docs are separated.
- Superseded specs are marked explicitly.
- Reference project docs record what to copy and what not to copy.
- Third-party provenance and license boundaries are recorded before source is copied.
- LGPL-covered or non-MIT-compatible components are isolated behind a dependency,
  adapter, or explicit legal review.

### Phase 1: Polymarket adapter validation
- Validate the current SDK path before strategy implementation.
- Prefer `py-clob-client-v2` / unified SDK semantics over archived clients.
- Document public, L1, L2, builder, and user-channel auth separately.
- Document asset ID vs condition ID usage for market and user WebSocket channels.
- Document heartbeat behavior and reconnect/reconciliation requirements.
- Add adapter conformance checks for CLOB, Gamma/Data API, WebSocket, signing,
  split, merge, redeem, and on-chain balance reads.

### Phase 2: Domain contracts and architecture spine
- Freeze `OrderIntent`, `CancelIntent`, `ExpectedOrderDelta`,
  `WorkflowCommand`, `PortfolioTarget`, `FillEvent`, `LedgerEntry`, and
  `RiskDecision` contracts.
- Strategies produce intents, expected-order deltas, portfolio targets, or
  workflow commands.
- Executors own CLOB transport, retries, cancellations, and order state mutation.
- Wallet/chain adapters own split, merge, redeem, approvals, and on-chain balance reads.
- Risk gates sit between strategy decisions and execution.
- Storage ports cover snapshots, positions, paper ledger, dedupe sets, open
  intents, exchange order IDs, pending cancels, partial fills, and recovery state.
- Package boundaries enforce that research, strategy, execution, reconciliation,
  and AI Studio depend inward on contracts rather than on each other.

### Phase 3: Execution, reconciliation, and paper runtime
- Implement the intent executor before live strategy ports.
- Implement post-only/taker execution policies with explicit queue, latency,
  partial-fill, timeout, cancel-verification, and adverse-selection assumptions.
- Implement WebSocket wake-up plus CLOB cross-check plus on-chain balance truth.
- Persist paper fills, live fills, positions, open orders, dedupe markers, and
  restart recovery state outside process memory.
- Provide a sandbox/paper runtime shared by market-making workflows and factor strategies.
- Add preflight, dry-run/live confirmation, credential validation, log redaction,
  emergency stop, and per-market/per-token command serialization.

### Phase 4: Official MM port
- Port AMM and Bands pure math first.
- Preserve snapshot to expected-orders to executor boundary.
- Carry over strategy invariant tests: ladder symmetry, band overlap checks,
  cancel/replace semantics, band fill order, and graceful cancel-all lifecycle.
- Keep binary complement assumptions scoped to official-keeper adapters or
  strategy packages.
- Prove source parity on representative snapshots before live/paper promotion.

### Phase 5: Terminal and event workflows
- Model Maker Rebate, Event MM, Sniper, Copy Trade, and Classic MM as separate
  bounded workflows, not all as market-making strategy subclasses.
- Each workflow needs a state-machine document before implementation.
- Shared pair lifecycle covers YES/NO inventory, split, merge, redeem, one-sided
  halt, sell-remainder, and resolved-position redemption.
- Fill detection uses WebSocket events as wake-up signals and on-chain balances
  as reconciliation truth.
- Per-market or per-asset serialization is required before placing/canceling
  live orders.
- Preserve simulation mode and operator runtime assumptions from reference workflows.

### Phase 6: Factor data and research engine
- Build CLOB-native snapshot store before factor strategies.
- Add DuckDB-style research panels for markets, outcomes, orderbook snapshots,
  trades, holders, resolutions, returns, fee regimes, and data-quality reports.
- Implement universe construction, snapshot integrity checks, feature panels,
  tradability filters, score normalization, ranking, portfolio construction, and
  attribution as separate ports.
- Implement executable-price backtesting before live/paper factor promotion.
- Include spread, depth, tick size, fees, latency, order type, queue position,
  adverse selection, capacity, and partial-fill assumptions.
- Reject midpoint-only backtests as evidence for tradability.

### Phase 7: Factor strategies and promotion governance
- Momentum, regime/volatility, sentiment, fair-value/microstructure, structural
  relative-value, composite, and hedge overlays start only after Phase 6 gates pass.
- Volume, spread, depth, fees, freshness, and time-to-resolution are tradability
  filters unless a strategy document proves they are predictive signals.
- Each factor report separates signal evidence from execution evidence.
- Each promoted factor includes executable-price backtest, walk-forward results,
  bootstrap or confidence-interval evidence, paper OMS results, capacity analysis,
  execution-sensitivity report, and failure analysis.
- PASS, FAIL, NO EDGE, and INCONCLUSIVE are valid research outcomes.

### Phase 8: AI studio
- Natural language maps to typed strategy configuration only.
- LLM output never bypasses schema validation, implementation-status checks,
  risk checks, preflight checks, paper/live gates, or promotion status.
- AI factor discovery proposes research candidates; it does not directly promote
  live strategies.
- Generated configurations include provenance, source strategy version, risk
  limits, and execution policy.

### Phase 9: Operator readiness, release, and expansion
- Documentation site.
- CI pipeline for docs, lint, tests, security scan, license/provenance checks,
  adapter conformance, and factor regression.
- Operator dashboard or reports for fills, positions, reconciliation gaps, P&L
  decomposition, decile spread, capacity, and alerts.
- PyPI release only after the public package exposes implemented modules rather
  than target-only facades.
- Strategy templates gallery.
- Plugin system and multi-platform research are explicit extensions; Kalshi,
  Limitless, and other venues require venue-specific adapter and data gates.

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

### Why Python as the primary application stack

Single-language application code keeps packaging, deployment, and agent-driven
maintenance simple. The merged projects are not all Python, however:
`probablyprofit-ai-framework`, `pm-official-mm-keeper`, `warproxxx-mm-bot`,
`Polymarket-Edge-Research`, `prediction-market-backtesting`, and
`polymarket-quant` are Python-centered; `pm-terminal-all-in-one` is Node.js;
`polymarket-cross-sectional-momentum` is TypeScript; and
`prediction-market-backtesting` also contains NautilusTrader/Rust-adjacent
data-loading and LGPL-scoped extension concerns.

TypeScript/Node logic is ported to Python only behind parity gates. The goal is
not line-for-line translation; it is preserving strategy semantics, execution
assumptions, reconciliation behavior, and failure-mode handling.

### Factor strategies use execution-aware bridges

**Critical lesson from recallnet/polymarket-cross-sectional-momentum**:
midpoint-based backtesting systematically overstates returns. CLOB bid-ask
spread can exceed the factor signal. Polymind factor strategies therefore
produce portfolio targets or order intents and pass them through an execution
bridge. The bridge may use passive market-making mechanics, but factor
strategies do not inherit market-making strategy semantics.

### Factor pipeline is real-time, not batch

The reference project collected snapshots on a timer and ran scoring on each
cycle. Polymind's factor pipeline runs continuously: new snapshots → validate
freshness → update features → apply tradability filters → update factor scores
→ construct portfolio targets → emit order intents. This allows tighter
integration with execution and reconciliation infrastructure without hiding
execution assumptions inside the factor score.

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
| `probablyprofit-ai-framework` | Composition-root CLI, agent loop, risk/storage/backtesting boundaries, paper/live separation, plugin lessons | Hidden singleton dependencies, over-broad public facade, AI output that bypasses typed schemas or risk gates |
| `pm-official-mm-keeper` | Snapshot to expected-orders to executor split; AMM/Bands invariants; graceful cancel/replace lifecycle | Positional config unpacking, in-place band mutation, universal order identity based only on price/side/token |
| `warproxxx-mm-bot` | Event-driven shell, explicit merge/cooldown/risk concepts, operator parameterization lessons | Global mutable state, monolithic `trading.py`, business logic in WebSocket callbacks |
| `pm-terminal-all-in-one` | Workflow-specific state machines, simulation modes, ghost-fill recovery, on-chain reconciliation, scheduler lessons | Shared mutable config and JSON state embedded in services, callback injection, treating all workflows as generic trader flags |
| `polymarket-cross-sectional-momentum` | CLOB snapshot store, scanner shape, paper scaffold, postmortem discipline, experiment tombstones | Midpoint-only backtests, market-order factor execution, static cost haircuts, replay contamination |
| `Polymarket-Edge-Research` | DuckDB panels, resolution truth, walk-forward validation, deployment gates, structural edge families | Treating factor panels as execution proof or PASS as guaranteed profitability |
| `prediction-market-backtesting` | Nautilus-backed replay concepts, passive order modeling, queue/latency/partial-fill realism, multi-market reports | Copying LGPL-scoped code into MIT-only package, assuming generic backtest fills match Polymarket CLOB execution |
| `polymarket-quant` | Orderbook state → fair value → executable edge, micro-price, latent state, regime and cross-book features | Treating fair-value estimates or midpoint-like references as executable prices |

Detailed evidence belongs in `docs/references/`.

### `recallnet/polymarket-cross-sectional-momentum`

| Aspect | Finding | Polymind Response |
|--------|---------|------------------|
| Momentum signal | Real (6.19 Sharpe backtest) | Implement momentum factor with multiple lookbacks |
| Execution cost | 2–10% spread kills edge | Factor strategies use executable-price models and documented passive/taker execution assumptions |
| Midpoint prices | Untradeable reference price | Backtest against CLOB bid/ask only; never Gamma midpoint |
| Hold period | Short holds amplify cost | Hold periods configurable per factor (1h–21d) |
| CLOB data pipeline | Collector + JSONL store worked correctly | Reuse `collect → appendSnapshot → readSnapshots` pattern |
| Data pipeline design | Collect mid/bid/ask per token as JSONL | Adopt the same JSONL snapshot store in `storage/price_store.py` |
| Paper trading scaffold | Dedup, budget enforcement, fill tracking | Integrate into backtesting engine |
| **−13.6% live PnL** | **18 trades, 11% hit rate** | **Hybrid factor execution: directional signal + execution-aware bridge** |

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

These are extensions after the Phase 0–9 gates, not prerequisites for the
initial Polymarket release:

- **Additional venues**: Kalshi, Limitless, Metaculus. Each requires venue-
  specific data, execution, reconciliation, fee, and compliance gates.
- **Third-party plugin ecosystem**: pip-installable factors and workflows after
  the core contracts are stable.
- **Advanced auto-factor discovery**: ML/LLM proposes factor definitions,
  backtests them, reports IC/Sharpe, and sends candidates through the same
  promotion gates as human-authored strategies.
