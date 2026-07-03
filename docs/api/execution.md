# Execution API

The `polymind.execution` package provides venue-neutral execution orchestration:
intent-to-order lifecycle, fill simulation, and deterministic order identity.

## Module Overview

```
polymind.execution
├── executor.py        — PaperExecutor, OrderRecord, OrderStatus, PositionRecord
├── fill_model.py      — FillMode, FillModel, FillModelConfig, MarketSnapshot, FillResult
├── order_identity.py  — OrderIdentity (frozen, deterministic)
└── serializer.py      — OrderSerializer, SerializerConfig, SerializedOrder
```

Public exports via `__init__.py`:

```python
from polymind.execution import (
    FillMode,
    FillModel,
    FillModelConfig,
    FillResult,
    MarketSnapshot,
    OrderIdentity,
    OrderRecord,
    OrderStatus,
    PaperExecutor,
    PositionRecord,
)
```

## PaperExecutor

`class polymind.execution.executor.PaperExecutor`

In-memory paper/sandbox executor implementing `IntentExecutor`. Simulates the
order lifecycle entirely in memory using a `FillModel`. No exchange credentials
or network access required.

### Order Lifecycle

| State | Description |
|-------|-------------|
| `OrderStatus.OPEN` | Order placed, no fills yet |
| `OrderStatus.PARTIALLY_FILLED` | Order partially filled |
| `OrderStatus.FILLED` | Order fully filled |
| `OrderStatus.CANCELLED` | Order cancelled |

### Related Types

```python
@dataclass
class OrderRecord:
    identity: OrderIdentity
    intent: OrderIntent
    status: OrderStatus
    created_at: datetime
    filled_size: float = 0.0
    filled_value: float = 0.0
    cancelled_size: float = 0.0
    last_tick: datetime | None = None

@dataclass
class PositionRecord:
    market_id: str
    outcome: str | None
    side: OrderSide
    total_filled: float = 0.0
    total_value: float = 0.0
    net_size: float = 0.0
    average_price: float = 0.0
```

## FillModel

`class polymind.execution.fill_model.FillModel`

Encapsulates assumptions about how a limit order fills: passive (waits in queue,
may fill partially or fully) vs. taker (immediate fill at executable price).

### FillMode

| Mode | Description |
|------|-------------|
| `FillMode.PASSIVE` | Limit order, filled when price crosses |
| `FillMode.TAKER` | Marketable limit / immediate fill at bid/ask |

### FillModelConfig

| Field | Default | Description |
|-------|---------|-------------|
| `mode` | `PASSIVE` | Execution mode |
| `maker_fee_rate` | `0.0` | Maker fee (e.g. 0.001 for 0.1%) |
| `taker_fee_rate` | `0.003` | Taker fee (e.g. 0.003 for 0.3%) |
| `slippage_bps` | `0.0` | Additional slippage for taker fills |
| `queue_position_pct` | `0.5` | Assumed queue position (0.0–1.0) |
| `partial_fill_probability` | `0.0` | Probability of partial fill per tick |

### Types

```python
@dataclass
class MarketSnapshot:
    market_id: str
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    mid_price: float
    timestamp: datetime

@dataclass
class FillResult:
    filled: bool
    fill_price: float | None = None
    fill_size: float = 0.0
    fee: float = 0.0
    remaining_size: float = 0.0
    partial: bool = False
```

## OrderIdentity

`class polymind.execution.order_identity.OrderIdentity`

Stable, deterministic order identity for the entire order lifecycle. An
`OrderIdentity` is **frozen** and derived from the intent payload so the
same intent produces the same identity across restarts.

```python
@dataclass(frozen=True)
class OrderIdentity:
    strategy_name: str
    market_id: str
    side: OrderSide
    price: float
    outcome: str | None
    client_id: str

    def to_identity_string(self) -> str
```

The `to_identity_string()` method returns a canonical string for logging and
SDK `exchange_order_id`:
`"strategy_name:market_id:BUY:0.50:outcome:client_id"`.

## Serializer

The `serializer.py` module provides per-market / per-token command serialization
to ensure that orders are correctly formatted for the Polymarket CLOB, handling
token ID resolution, chain ID, and signature parameters.
