# Core API

The `polymind.core` package provides the foundational abstractions for all Polymind
strategies: the agent loop, configuration, strategy base classes, intents, risk gates,
and workflow commands.

## Module Overview

```
polymind.core
├── agent.py      — BaseAgent (observe → decide → act)
├── config.py     — Configuration management
├── fills.py      — FillEvent, FillSource
├── intents.py    — StrategyIntent, OrderIntent, CancelIntent, IntentExecutor
├── ledger.py     — LedgerEntry, EntryType
├── portfolio.py  — PortfolioTarget, PositionDirection
├── risk.py       — RiskContext, RiskDecision, RiskGate
├── strategy.py   — BaseMMStrategy, StrategyConfig, StrategySignal
└── workflows.py  — WorkflowCommand, CommandType
```

Public exports via `__init__.py`:

```python
from polymind.core import (
    BaseAgent,          # agent.py
    BaseMMStrategy,     # strategy.py
    CommandType,        # workflows.py
    Config,             # config.py
    EntryType,          # ledger.py
    FillEvent,          # fills.py
    FillSource,         # fills.py
    IntentExecutor,     # intents.py
    LedgerEntry,        # ledger.py
    PortfolioTarget,    # portfolio.py
    PositionDirection,  # portfolio.py
    RiskContext,        # risk.py
    RiskDecision,       # risk.py
    RiskGate,           # risk.py
    StrategyIntent,     # intents.py
    WorkflowCommand,    # workflows.py
)
```

## BaseAgent

`class polymind.core.agent.BaseAgent`

The core loop abstraction implementing `observe → decide → act`. Subclasses
must implement `decide()` with their trading logic.

### Constructor

```python
def __init__(
    self,
    client: Any = None,
    risk_manager: Any = None,
    name: str = "BaseAgent",
    loop_interval: int = 60,
    dry_run: bool = False,
)
```

### Methods

| Method | Description |
|--------|-------------|
| `observe()` | Fetch current market state — calls `client.get_markets()`, `get_positions()`, `get_balance()` if available. Returns an `Observation`. |
| `decide(observation)` | **Abstract** — make a `Decision` (action, market_id, outcome, size, price, reasoning, confidence). |
| `act(decision)` | Execute a trading decision. In dry-run mode or on "hold" it returns `True` without side effects. |
| `run_loop()` | Main loop: `observe() → decide() → act()` with `asyncio.sleep(loop_interval)` between ticks. |
| `stop()` | Set `_running = False` to break the loop. |

### Reference Types

```python
class Observation(BaseModel):
    timestamp: datetime
    markets: list[Any] = []
    positions: list[Any] = []
    balance: float = 0.0

class Decision(BaseModel):
    action: str  # "buy", "sell", "hold", "close"
    market_id: str | None = None
    outcome: str | None = None
    size: float = 0.0
    price: float | None = None
    reasoning: str = ""
    confidence: float = 0.5
```

## BaseMMStrategy

`class polymind.core.strategy.BaseMMStrategy`

Abstract base for all market-making strategies. A strategy defines which markets
to trade, how to price orders, how to size orders, and how to manage risk.

**Per ADR 0002**, strategies produce `StrategyIntent` objects; executors own
CLOB transport, retries, and order lifecycle.

### Constructor

```python
def __init__(self, config: StrategyConfig | None = None)
```

### Methods

| Method | Description |
|--------|-------------|
| `analyze(market)` | **Abstract (primary)** — analyze a market and produce a `StrategyIntent` or `None`. |
| `analyze_to_signal(market)` | Legacy analysis returning `StrategySignal`. Default implementation delegates to `analyze()`. |
| `manage_positions()` | Manage existing positions (take profit, stop loss, merge). |
| `risk_check()` | Check if strategy should continue operating. Return `False` to trigger emergency stop. |
| `get_config_summary()` | Return human-readable config summary dict. |

### Related Types

```python
@dataclass
class StrategyConfig:
    name: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)

@dataclass
class StrategySignal:
    action: str          # "place", "cancel", "hold", "close"
    market_id: str
    outcome: str | None = None
    side: str | None = None
    price: float | None = None
    size: float = 0.0
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
```

## StrategyIntent & OrderIntent (ADR 0002)

`polymind.core.intents`

Strategies produce intents; executors own CLOB transport, retries, and
cancellations. This is the contract between strategy policy and
exchange-specific implementation.

### Intent Types

| Class | Description |
|-------|-------------|
| `OrderIntent` | Intent to place a limit order on the CLOB. Fields: `market_id`, `side` (OrderSide), `price`, `size`, `outcome`, `time_in_force`, `expiration`, `reduce_only`, `metadata`. |
| `CancelIntent` | Intent to cancel one or more open orders. `order_id=None` cancels all orders for the market. |
| `StrategyIntent` | Complete output of a strategy's analysis tick: a list of `orders`, `cancels`, optional `risk_override`, and `metadata`. Has an `is_empty()` helper. |

### Enums

| Enum | Values |
|------|--------|
| `IntentType` | PLACE_ORDER, CANCEL_ORDER, CANCEL_ALL, HOLD, CLOSE_POSITION |
| `OrderSide` | BUY, SELL |
| `TimeInForce` | GTC (Good-Till-Cancelled), IOC (Immediate-Or-Cancel), FOK (Fill-Or-Kill) |

### IntentExecutor

```python
class IntentExecutor(ABC):
    async def execute(self, intent: StrategyIntent) -> dict[str, Any]
    async def dry_run(self, intent: StrategyIntent) -> dict[str, Any]
    async def shutdown(self) -> None
```

The executor translates `StrategyIntent` objects into SDK calls, handling
retries, error mapping, fill tracking, and order-state mutation.

## Risk Gates

`polymind.core.risk`

| Class | Description |
|-------|-------------|
| `RiskContext` | Current state for risk evaluation (positions, balance, exposure). |
| `RiskDecision` | Decision from a risk gate — `approved: bool` with a `reason: str`. |
| `RiskGate` | Abstract base for risk checks that sit between strategy intents and execution. |

## Fill Events

`polymind.core.fills`

| Class | Description |
|-------|-------------|
| `FillEvent` | Represents a completed fill: `market_id`, `outcome`, `side`, `size`, `price`, `timestamp`. |
| `FillSource` | Enum: CLOB, WEBSOCKET, ONCHAIN, BACKTEST |

## Ledger

`polymind.core.ledger`

| Class | Description |
|-------|-------------|
| `LedgerEntry` | Immutable log entry for fills and balance changes. |
| `EntryType` | Enum: FILL, TRANSFER, FEE, MERGE, SPLIT, REDEEM |

## Portfolio

`polymind.core.portfolio`

| Class | Description |
|-------|-------------|
| `PortfolioTarget` | Desired portfolio state with target positions per market/outcome. |
| `PositionDirection` | Enum: LONG, SHORT, NEUTRAL |

## Workflows

`polymind.core.workflows`

| Class | Description |
|-------|-------------|
| `WorkflowCommand` | Command to start/stop/pause/resume a trading workflow. |
| `CommandType` | Enum: START, STOP, PAUSE, RESUME, RESTART |

## Config

`polymind.core.config.Config`

Configuration management using Pydantic-based settings with YAML and environment
variable support. Handles strategy configuration, exchange credentials, and
runtime parameters.
