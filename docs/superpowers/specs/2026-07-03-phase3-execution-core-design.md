# Phase 3 Execution Layer Core — Design Spec

**Status:** Draft  
**Date:** 2026-07-03  
**ADR:** ADR 0002 (Strategies emit intents; executors place orders)

## 1. Overview

This spec defines the core of Phase 3: the execution layer that sits between
strategy intents and exchange-specific transport. It provides three components:

1. **OrderIdentity** — a stable, deterministic identity for every order intent,
   used for deduplication, audit, and cancel/replace.
2. **FillModel** — abstracts fill assumptions (passive vs. taker) for paper
   trading and backtesting.
3. **PaperExecutor** — a concrete `IntentExecutor` that simulates order
   placement and fill detection in memory, recording `FillEvent` and
   `LedgerEntry` outputs.

These components form the sandbox/paper runtime that all strategies use before
live promotion. They do not depend on the Polymarket CLOB SDK.

## 2. Package Layout

```
polymind/execution/
├── __init__.py
├── order_identity.py     # OrderIdentity
├── fill_model.py         # FillModel, FillModelConfig, FillResult
└── executor.py           # PaperExecutor (implements IntentExecutor)
```

## 3. Components

### 3.1 OrderIdentity — stable order identity

**File:** `polymind/execution/order_identity.py`

An `OrderIdentity` uniquely identifies an order intent for its entire
lifecycle: creation, acknowledgment, fill, cancel, and replace. It must be
deterministic from the intent payload so the same intent produces the same
identity across restarts.

```python
@dataclass(frozen=True)
class OrderIdentity:
    """Immutable, deterministic identity for an order intent.

    The identity is derived from the strategy name, market, side, price,
    and a strategy-chosen nonce/client_id.  Two OrderIntents with the
    same fields produce the same OrderIdentity, enabling safe
    cancel/replace without exchange round-trips.

    ``client_id`` is a strategy-chosen unique string (e.g. UUID, counter,
    or hash of the strategy's analysis tick).  Strategies must ensure
    client_id is unique within the (strategy_name, market_id) scope to
    avoid collisions.
    """
    strategy_name: str
    market_id: str
    side: OrderSide
    price: float
    outcome: Optional[str]
    client_id: str    # unique within (strategy_name, market_id) scope

    def to_identity_string(self) -> str:
        """Return a canonical string for logging and SDK exchange_order_id."""
        return f"{self.strategy_name}:{self.market_id}:{self.side.value}:{self.price}:{self.outcome or '_'}:{self.client_id}"
```

**Why frozen?** OrderIdentity must be usable as a dict key (for open-orders
maps) and hashable for set membership checks.

### 3.2 FillModel — fill simulation assumptions

**File:** `polymind/execution/fill_model.py`

A `FillModel` encapsulates the assumptions about how a limit order fills:
passive (waits in queue, may fill partially or fully) vs. taker (immediate
fill at executable price). This is the same model used by backtesting and
paper trading.

```python
@dataclass
class FillModelConfig:
    """Configuration for a FillModel."""
    mode: FillMode
    maker_fee_rate: float = 0.0       # e.g. 0.001 for 0.1%
    taker_fee_rate: float = 0.003     # e.g. 0.003 for 0.3%
    slippage_bps: float = 0.0         # additional slippage for taker fills
    queue_position_pct: float = 0.5   # assumed queue position (0.0–1.0)
    partial_fill_probability: float = 0.0  # probability of partial fill per tick


class FillMode(Enum):
    PASSIVE = auto()   # limit order, filled when price crosses
    TAKER = auto()     # marketable limit / immediate fill at bid/ask


@dataclass
class FillResult:
    """Outcome of a fill simulation."""
    filled: bool
    fill_price: float
    fill_size: float
    fee: float
    remaining_size: float
    timestamp: datetime


class FillModel:
    """Simulate fill outcomes for an order intent.

    In PASSIVE mode, fill depends on price crossing the spread and queue
    position.  In TAKER mode, fill is immediate at the executable price.
    """

    def __init__(self, config: FillModelConfig):
        self.config = config

    async def simulate(
        self,
        intent: OrderIntent,
        snapshot: "MarketSnapshot",   # bid/ask prices and sizes
    ) -> FillResult:
        """Return a FillResult based on the current snapshot."""
        ...

    def estimate_execution_price(
        self,
        side: OrderSide,
        snapshot: "MarketSnapshot",
    ) -> float:
        """Return the estimated execution price for a marketable order."""
        ...
```

**Key insight:** `simulate()` takes a market snapshot (bid/ask) and an
`OrderIntent` and returns a `FillResult`. It has no side effects. This makes
it testable from static snapshots.

### 3.3 MarketSnapshot — market state snapshot (forward definition)

A minimal snapshot type used by `FillModel` and `PaperExecutor`. Defined here
conceptually; the full snapshot type will live in `polymind/core/snapshot.py`
or similar in a future phase.

```python
@dataclass
class MarketSnapshot:
    """Minimal market snapshot for fill simulation."""
    market_id: str
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    mid_price: float
    timestamp: datetime
```

For this phase, tests can construct `MarketSnapshot` instances directly
without a collector or WebSocket feed.

### 3.4 PaperExecutor — in-memory sandbox executor

**File:** `polymind/execution/executor.py`

`PaperExecutor` is a concrete implementation of `IntentExecutor` that
simulates the order lifecycle entirely in memory. It uses `FillModel` to
simulate fills and records every event as `FillEvent` and `LedgerEntry`.

```python
class PaperExecutor(IntentExecutor):
    """In-memory paper/sandbox executor.

    Maintains an internal order book, simulates fills via FillModel,
    and records FillEvents and LedgerEntries.  No exchange credentials
    or network access required.
    """

    def __init__(
        self,
        fill_model: FillModel,
        initial_cash: float = 10_000.0,
        loop_interval: int = 60,
    ):
        self.fill_model = fill_model
        self.orders: Dict[str, OrderRecord] = {}    # identity_string → record
        self.fills: List[FillEvent] = []             # recorded fills
        self.ledger: List[LedgerEntry] = []          # recorded ledger entries
        self.cash: float = initial_cash
        self.positions: Dict[str, PositionRecord] = {}
        self.loop_interval = loop_interval

    async def execute(self, intent: StrategyIntent) -> Dict[str, Any]:
        """Process a StrategyIntent: place orders, cancel orders, simulate ticks.

        For each OrderIntent:
          1. Derive OrderIdentity → check if already open → dedupe.
          2. If new, create OrderRecord with status=OPEN.
          3. On each tick (or on demand), apply FillModel.simulate().
          4. If filled, record FillEvent + LedgerEntry.
          5. For each CancelIntent, mark orders as CANCELLED.

        Returns a summary dict per market_id.
        """
        ...

    async def simulate_tick(self, snapshot: "MarketSnapshot") -> int:
        """Simulate one market-data tick for all open orders.

        Returns the number of fills that occurred.
        """
        ...

    def get_position(self, market_id: str) -> Optional[PositionRecord]:
        """Return current position for a market (paper)."""
        ...

    def get_open_order_count(self) -> int:
        """Return number of currently open orders."""
        ...
```

**State records (internal):**

```python
@dataclass
class OrderRecord:
    """Internal record of an order in the paper executor."""
    identity: OrderIdentity
    intent: OrderIntent
    status: OrderStatus
    created_at: datetime
    filled_size: float = 0.0
    filled_value: float = 0.0
    cancelled_size: float = 0.0
    last_tick: Optional[datetime] = None


class OrderStatus(Enum):
    OPEN = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    CANCELLED = auto()


@dataclass
class PositionRecord:
    """Current position for a single market."""
    market_id: str
    outcome: str
    size: float          # positive = long, negative = short
    avg_entry: float
    realized_pnl: float
```

## 4. Integration Points

- **FillEvent** (`polymind/core/fills.py`) — PaperExecutor records fills as
  FillEvents, the standard unit for the reconciliation layer.
- **LedgerEntry** (`polymind/core/ledger.py`) — Every fill produces a
  LedgerEntry for P&L tracking.
- **StrategyIntent** (`polymind/core/intents.py`) — The input to execute().
- **OrderIdentity** — Bridges StrategyIntent and exchange order_id. Used by
  the PaperExecutor for dedupe and by future CLOB executors for cancel/replace.

## 5. Test Plan

| Test file | Tests |
|---|---|
| `tests/execution/test_order_identity.py` | Construction, immutability, hashability, identity_string format, deterministic from same fields |
| `tests/execution/test_fill_model.py` | FillModelConfig defaults, passive vs taker fill simulation, execution price estimation, fee calculation |
| `tests/execution/test_paper_executor.py` | Execute StrategyIntent → orders placed, duplicate dedupe, cancel works, simulated tick produces fills, FillEvent recording, LedgerEntry recording, position tracking, cash balance updates |

## 6. Future Extensions (not in this spec)

- **Live CLOB executor** — wraps the Polymarket SDK, uses OrderIdentity for
  cancel/replace, maps FillEvent from real WebSocket events.
- **Serializer** — per-market/per-token command serialization (Phase 4-5).
- **Persistence** — SQLite/duckdb backend for PaperExecutor state (Phase 3
  full).
- **Reconciliation layer** — WebSocket wake-up + CLOB cross-check + on-chain
  balance truth.
