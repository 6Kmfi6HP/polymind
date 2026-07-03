# Polymarket API

The `polymind.polymarket` package provides Polymarket CLOB integration adapters:
order management, real-time data, market metadata, smart contracts, signing,
and instrumentation.

## Module Overview

```
polymind.polymarket
├── __init__.py     — Public exports
├── client.py       — PolymarketClient (CLOB SDK wrapper)
├── websocket.py    — PolymarketWebSocketAdapter (realtime feed)
├── data_api.py     — PolymarketDataAPI (Gamma/Data API metadata, history)
├── contracts.py    — ContractsGateway (split, merge, redeem, balance)
├── signer.py       — Signer, ApiKeyCredentials, WalletCredentials, AuthTier
└── metrics.py      — AdapterMetrics, Counter, Histogram, MetricsSummary
```

Public exports via `__init__.py`:

```python
from polymind.polymarket import (
    AdapterMetrics,
    ApiKeyCredentials,
    AuthTier,
    Candle,
    ContractsConfig,
    ContractsGateway,
    Counter,
    DataAPIConfig,
    Histogram,
    MarketDetail,
    MarketEvent,
    MergeResult,
    MetricsSummary,
    OrderLevel,
    OrderbookSnapshot,
    PolymarketClient,
    PolymarketDataAPI,
    PolymarketWebSocketAdapter,
    RedeemResult,
    Signer,
    SplitResult,
    TokenBalance,
    Trade,
    VolumeInfo,
    WebSocketChannel,
    WebSocketConfig,
)
```

## PolymarketClient

`class polymind.polymarket.client.PolymarketClient`

Wraps `py-clob-client` for Polymarket CLOB API access. Supports both regular
and negative-risk markets.

### Methods

| Method | Description |
|--------|-------------|
| `get_markets(active, limit)` | Fetch active markets from Polymarket |
| `get_positions()` | Fetch open positions |
| `get_balance()` | Fetch USDC balance |
| `place_order(**kwargs)` | Place an order on the CLOB |
| `cancel_order(order_id)` | Cancel a specific order |
| `cancel_all_orders()` | Cancel all open orders |
| `close()` | Close the client connection |

## PolymarketWebSocketAdapter

`class polymind.polymarket.websocket.PolymarketWebSocketAdapter`

WebSocket adapter for real-time Polymarket market data and user events.
Manages connection lifecycle, channel subscriptions, automatic reconnection,
and delivers parsed `MarketEvent` objects via an async generator.

### WebSocketChannel

| Channel | Description |
|---------|-------------|
| `USER_FILL` | User fill events |
| `USER_ORDER` | User order updates |
| `BOOK` | Order book snapshots and updates |
| `TICKER` | Ticker updates |
| `LAST_TRADE_PRICE` | Last trade price updates |

### Types

```python
@dataclass
class WebSocketConfig:
    url: str
    channels: list[WebSocketChannel]
    auth_token: str | None = None
    reconnect_delay: float = 1.0
    max_reconnects: int = 5

@dataclass(frozen=True)
class MarketEvent:
    market_id: str
    channel: WebSocketChannel
    event_type: str
    data: dict
    timestamp: datetime
```

## PolymarketDataAPI

`class polymind.polymarket.data_api.PolymarketDataAPI`

Adapter for the Polymarket Data API (Gamma API). Provides domain-typed
responses for factor engines, backtesting, and strategy analysis.

### Types

| Class | Description |
|-------|-------------|
| `MarketDetail` | Full market metadata (title, outcomes, volume, liquidity, tick_size) |
| `OrderbookSnapshot` | Point-in-time order book (bids, asks, timestamp) |
| `OrderLevel` | Single bid/ask level (price, size) |
| `Candle` | OHLCV candlestick data |
| `Trade` | A single trade record |
| `VolumeInfo` | Volume statistics |
| `DataAPIConfig` | Configuration for the Data API adapter |

## ContractsGateway

`class polymind.polymarket.contracts.ContractsGateway`

Encapsulates all on-chain interactions (ERC-1155, CTF Exchange) behind
project-owned domain types. Strategy code must never call contracts directly.

### Methods

| Method | Description |
|--------|-------------|
| `split(market, amount)` | Split outcome tokens into component tokens |
| `merge(market, amount_a, amount_b)` | Merge outcome tokens back into parent |
| `redeem(market)` | Redeem winning tokens after resolution |
| `get_balance(token_id)` | Get ERC-1155 balance for a token |

### Result Types

| Class | Description |
|-------|-------------|
| `SplitResult` | tx_hash, outcome_a_amount, outcome_b_amount, timestamp |
| `MergeResult` | tx_hash, outcome_a_amount, outcome_b_amount, timestamp |
| `RedeemResult` | tx_hash, proceeds_usdc, timestamp |
| `TokenBalance` | token_id, owner, balance |
| `ContractsConfig` | Configuration for contracts gateway |

## Signer

`class polymind.polymarket.signer.Signer`

Authentication and signing for Polymarket API access. Encapsulates the three
auth tiers as defined in ADR 0003 / ADR 0004.

### AuthTier

| Tier | Description |
|------|-------------|
| `PUBLIC` | Public endpoints, no auth required |
| `API_KEY` | L2 authenticated endpoints |
| `WALLET` | On-chain operations requiring wallet signing |

### Credential Types

```python
@dataclass(frozen=True)
class ApiKeyCredentials:
    api_key: str
    api_secret: str
    api_passphrase: str

@dataclass(frozen=True)
class WalletCredentials:
    private_key: str
```

## AdapterMetrics

`class polymind.polymarket.metrics.AdapterMetrics`

Collector for adapter-level instrumentation. Each adapter module creates its
own instance with a unique prefix.

### Aggregated Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `calls_total` | `Counter` | Total API calls |
| `errors_total` | `Counter` | Total errors |
| `retries_total` | `Counter` | Total retries |
| `latency_seconds` | `Histogram` | Latency distribution in seconds |
| `ws_disconnects_total` | `Counter` | WebSocket disconnections |
| `ws_reconnects_total` | `Counter` | WebSocket reconnections |
| `ws_messages_received` | `Counter` | WebSocket messages received |

### Key Methods

| Method | Description |
|--------|-------------|
| `record_request(method, endpoint, duration_ms, status_code)` | Record an API request |
| `record_error(method, endpoint, error_type)` | Record an error |
| `get_summary()` | Build a `MetricsSummary` snapshot |
| `measure()` | Context manager that records call duration |
