# Phase 2 Domain Contracts — Design Spec

**Status:** Draft  
**Date:** 2026-07-03  
**ADR:** ADR 0002 (Strategies emit intents; executors place orders)

## 1. Overview

This spec defines the remaining domain contracts required to freeze Phase 2 of
the Polymind architecture roadmap. These contracts sit between strategy policy
and exchange-specific execution, and are designed to be inspectable by risk
gates, storable in the paper/live ledger, and testable from immutable snapshots.

### Design Constraints

- Plain dataclasses or Pydantic models for serialization and inspection.
- Timezone-aware `datetime` with UTC for all timestamp fields.
- Existing patterns in `polymind/core/intents.py` are the canonical reference.
- No exchange-specific types leak into these contracts.
- Each contract has a distinct responsibility; none inherits from another.

## 2. Contracts

### 2.1 `PortfolioTarget`

**File:** `polymind/core/portfolio.py`

Represents the output of a factor strategy's portfolio construction step:
which markets to hold positions in, at what size and direction, and with what
priority.

```python
@dataclass
class PortfolioTarget:
    """A desired portfolio position produced by a factor or overlay strategy.

    Factor strategies compute signal scores, rank markets, apply filters,
    and produce a set of PortfolioTargets.  An execution bridge converts
    these into OrderIntents for the executor.
    """
    market_id: str
    direction: PositionDirection  # LONG, SHORT, NEUTRAL
    target_size: float            # in token/Shares (not USD)
    confidence: float             # 0.0–1.0, from signal score
    rank: int                     # decile / percentile rank among universe
    holding_period_hours: Optional[float] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class PositionDirection(Enum):
    LONG = auto()
    SHORT = auto()
    NEUTRAL = auto()
```

### 2.2 `FillEvent`

**File:** `polymind/core/fills.py`

A unified representation of a fill or partial fill, regardless of whether it
was detected via WebSocket event, CLOB API poll, or on-chain balance
reconciliation.

```python
@dataclass
class FillEvent:
    """A fill or partial fill detected by any channel.

    The reconciliation layer uses FillEvent as the standard unit; WebSocket
    events, CLOB API responses, and on-chain balance diffs are all normalized
    to this shape before the ledger processes them.
    """
    fill_id: str                    # unique (exchange-assigned or local)
    market_id: str
    outcome: str                    # "YES" or "NO"
    side: OrderSide
    price: float
    size: float
    fee: float
    timestamp: datetime             # exchange-reported (or local if unavailable)
    source: FillSource              # WEBSOCKET, CLOB_API, ONCHAIN, SIMULATED
    order_id: Optional[str] = None  # exchange order ID
    taker: bool = False             # True = this fill was a taker order
    metadata: Dict[str, Any] = field(default_factory=dict)


class FillSource(Enum):
    WEBSOCKET = auto()
    CLOB_API = auto()
    ONCHAIN = auto()
    SIMULATED = auto()
```

### 2.3 `LedgerEntry`

**File:** `polymind/core/ledger.py`

An append-only entry in the paper or live P&L ledger. Each entry records a
monetary event: a fill, a fee, a merge/split/redeem, or a cash adjustment.

```python
@dataclass
class LedgerEntry:
    """Immutable record of a value-changing event.

    The ledger is append-only.  Once written, an entry is never mutated;
    corrections produce new entries with a reference to the superseded one.
    """
    entry_id: str                   # globally unique, monotonically increasing
    entry_type: EntryType
    timestamp: datetime
    market_id: str
    description: str
    delta_cash: float               # change in cash balance (+/-)
    delta_position: float           # change in position size (+/-)
    position_after: float           # resulting position size
    cash_after: float               # resulting cash balance
    fill_ref: Optional[str] = None  # references FillEvent.fill_id
    supersedes: Optional[str] = None  # references superseded entry_id
    metadata: Dict[str, Any] = field(default_factory=dict)


class EntryType(Enum):
    FILL = auto()
    FEE = auto()
    MERGE = auto()
    SPLIT = auto()
    REDEEM = auto()
    CASH_ADJUSTMENT = auto()
    CORRECTION = auto()
```

### 2.4 `RiskDecision`

**File:** `polymind/core/risk.py`

The output of a risk gate evaluation. Each risk gate inspects a
`StrategyIntent` or `PortfolioTarget` and returns a `RiskDecision`:
approved, rejected, or reduced (with modified parameters).

```python
@dataclass
class RiskDecision:
    """Decision from a single risk gate.

    Risk gates are composable: a StrategyIntent passes through multiple gates
    (exposure limit, drawdown check, per-market cap, kill switch), and each
    gate returns its own decision.  The risk manager aggregates them.
    """
    gate_name: str                  # e.g. "exposure_limit", "drawdown_guard"
    approved: bool
    reason: str
    overrides: Optional[Dict[str, float]] = None  # modified risk params
    timestamp: datetime = MISSING   # set automatically on creation
```

**Implementation note:** `MISSING` is a sentinel; the actual implementation
uses `field(default_factory=lambda: datetime.now(timezone.utc))`.

```python
# Separate abstract base for risk gates (in the same file)
class RiskGate(ABC):
    """A single composable risk check."""
    name: str

    @abstractmethod
    async def evaluate(
        self,
        intent: StrategyIntent,
        context: RiskContext,
    ) -> RiskDecision:
        ...


@dataclass
class RiskContext:
    """Context provided to every risk gate."""
    current_positions: Dict[str, float]
    current_exposure: float
    daily_pnl: float
    is_kill_switch_active: bool
    portfolio_value: float
```

### 2.5 `WorkflowCommand`

**File:** `polymind/core/workflows.py`

A workflow-level instruction produced by the strategy engine or operator.
Workflows have lifecycle (start → run → pause → resume → stop) and may
produce sub-commands for pair lifecycle management.

```python
@dataclass
class WorkflowCommand:
    """A workflow lifecycle or pair-management command.

    Unlike OrderIntent (which targets a single market), WorkflowCommand
    targets an entire workflow instance.  The workflow runtime interprets
    the command and translates it into lower-level intents.
    """
    workflow_id: str
    command: CommandType
    reason: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = MISSING


class CommandType(Enum):
    START = auto()
    STOP = auto()
    PAUSE = auto()
    RESUME = auto()
    RESTART = auto()

    # Pair lifecycle (for Maker Rebate, Event MM etc.)
    SPLIT = auto()        # split USDC into YES/NO
    MERGE = auto()        # merge YES+NO back to USDC
    REDEEM = auto()       # redeem winning tokens
    SELL_REMAINDER = auto()  # sell dust/unresolved tokens
    ONE_SIDED_HALT = auto()  # halt one side of a paired position
```

**Implementation note:** `MISSING` is a sentinel; the actual implementation
uses `field(default_factory=lambda: datetime.now(timezone.utc))`.

## 3. Package Layout

```
polymind/core/
├── __init__.py
├── agent.py          # existing
├── config.py         # existing
├── intents.py        # existing (OrderIntent, CancelIntent, StrategyIntent, IntentExecutor)
├── strategy.py       # existing (BaseMMStrategy, StrategyConfig)
├── portfolio.py      # NEW  — PortfolioTarget, PositionDirection
├── fills.py          # NEW  — FillEvent, FillSource
├── ledger.py         # NEW  — LedgerEntry, EntryType
├── risk.py           # NEW  — RiskDecision, RiskGate, RiskContext
└── workflows.py      # NEW  — WorkflowCommand, CommandType
```

## 4. Test Plan

Each new module gets a dedicated test file in `tests/`:

| Test file | Tests |
|---|---|
| `tests/test_portfolio.py` | PortfolioTarget construction, defaults, serialization |
| `tests/test_fills.py` | FillEvent construction, source enum, fee handling |
| `tests/test_ledger.py` | LedgerEntry creation, cash/position deltas, supersedes chain |
| `tests/test_risk.py` | RiskDecision construction, RiskGate ABC, RiskContext, composability |
| `tests/test_workflows.py` | WorkflowCommand construction, command types, workflow_id |

Test patterns follow the existing `tests/test_intents.py` style:
- Plain dataclass construction with defaults
- Enum roundtrips
- ABC protocol conformance (concrete test stubs)

## 5. Future Integration Points

These contracts are designed to compose with downstream phases:

- **Phase 3 (Execution):** `FillEvent` feeds the reconciliation layer;
  `LedgerEntry` records executor actions.
- **Phase 4–5 (MM workflows):** `WorkflowCommand` drives pair lifecycle in
  Maker Rebate and Event MM workflows.
- **Phase 6 (Factor Engine):** `PortfolioTarget` is the output of the factor
  pipeline and input to `FactorExecutionBridge`.
- **Phase 7 (Promotion):** `RiskDecision` gates promotion from paper to live.

No forward references are imported from those phases at this point.
