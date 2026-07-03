# Phase 1 Polymarket Adapter Layer — Design Spec

**Status:** Draft  
**Date:** 2026-07-03  
**ADR:** ADR 0004 (SDK adapter isolated from core)

## 1. Overview

This spec defines the Polymarket adapter layer — the venue-specific boundary that
wraps `py-clob-client` behind async, project-owned interfaces. It implements
ADR 0004's mandate: **core strategy, factor, risk, and backtesting modules must
never import SDK types directly.**

The layer maps to three real Polymarket API surfaces:

1. **CLOB REST API** — market data (order books, tickers, trades), order
   management (place, cancel, replace), account queries (positions, balances).
   Wrapped by `client.py` and `data_api.py`.
2. **Polymarket WebSocket API** — public market streams (order books, trades,
   tickers) and authenticated user streams (fills, order status, account
   changes). Wrapped by `websocket.py`.
3. **Polygon on-chain contracts** — ERC-1155 conditional token operations
   (split, merge, redeem), collateral (USDC) approval and transfers, CTF
   exchange interactions. Wrapped by `contracts.py`.

Additionally, the layer provides:

- **`signer.py`** — encapsulates the three authentication tiers (public,
  API-key-authenticated, wallet/private-key-authenticated) so the rest of the
  adapter never touches raw key material.
- **`metrics.py`** — prometheus-compatible counters and histograms for adapter
  health (call latency, error rates, WebSocket disconnects).

**Design rules:**

- Every adapter method is async. Blocking SDK calls are dispatched via
  `asyncio.to_thread` or `loop.run_in_executor` when the SDK is synchronous.
- All public methods return domain types from `polymind.core.*`, never raw
  `py_clob_client.clob_types.*` objects. Internal mapping functions live in
  each module.
- No strategy logic leaks into adapters. Adapters are pure transport — they
  translate SDK bytes into domain objects and domain objects into SDK calls.
  They do not decide what to trade, when to trade, or how much.
- WebSocket reconnection uses asyncio tasks with exponential backoff, not
  SDK-internal retry.

## 2. Package Layout

```
polymind/polymarket/
├── __init__.py              # Package namespace, exports PolymarketClient
├── client.py                # CLOB REST adapter (orders, markets, positions)
├── websocket.py             # Public + authenticated WebSocket streams
├── data_api.py              # Gamma/Data API metadata, price history, candles
├── contracts.py             # On-chain operations (split, merge, redeem, approvals)
├── signer.py                # Auth credentials: API key, private key, wallet
└── metrics.py               # Prometheus counters and histograms
```

## 3. Modules

### 3.1 `signer.py` — Authentication credentials and signing

**File:** `polymind/polymarket/signer.py`

Encapsulates the three authentication tiers defined in ADR 0003 / ADR 0004.
The `Signer` class holds no more than one tier's credentials at a time and is
passed at construction to `PolymarketClient`, `WebSocketManager`, etc.

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class AuthTier(Enum):
    """Authentication level for Polymarket API access."""

    PUBLIC = auto()              # no credentials, market data only
    API_KEY = auto()             # API key + secret + passphrase (L2 auth)
    WALLET = auto()              # private key for on-chain operations


@dataclass(frozen=True)
class ApiKeyCredentials:
    """API-key-level credentials for L2 authenticated endpoints."""

    api_key: str
    api_secret: str
    api_passphrase: str


@dataclass(frozen=True)
class WalletCredentials:
    """Wallet-level credentials for on-chain operations."""

    private_key: str             # hex-encoded, with or without 0x prefix
    # Derived lazily: address is computed from private_key on first access.
    _address: Optional[str] = None

    @property
    def address(self) -> str:
        """Return the checksummed Ethereum address derived from private_key."""
        if self._address is None:
            ...
        return self._address


class Signer:
    """Holds credentials for one auth tier and provides signing operations.

    The Signer is immutable after construction.  Callers check ``tier`` to
    determine which operations are available:

    - PUBLIC:  market data only (get_markets, get_order_book, etc.)
    - API_KEY: adds order placement, cancellation, user-specific WebSocket.
    - WALLET:  adds on-chain operations (split, merge, redeem, approvals).

    The Signer does not perform network calls.  It is a pure-data + signing
    object that can be serialized/deserialized for config reload.
    """

    def __init__(
        self,
        tier: AuthTier,
        api_creds: Optional[ApiKeyCredentials] = None,
        wallet_creds: Optional[WalletCredentials] = None,
    ):
        self.tier = tier
        self.api_creds = api_creds
        self.wallet_creds = wallet_creds

    # ── Factory helpers ──────────────────────────────────────────────────

    @classmethod
    def public(cls) -> Signer:
        """Create a public-tier Signer (no credentials needed)."""
        ...

    @classmethod
    def from_api_key(cls, api_key: str, secret: str, passphrase: str) -> Signer:
        """Create an API-key-tier Signer."""
        ...

    @classmethod
    def from_wallet(cls, private_key: str) -> Signer:
        """Create a wallet-tier Signer (implies API-key + on-chain access)."""
        ...

    # ─── Signing (wallet tier) ───────────────────────────────────────────

    def sign_typed_data(self, domain: dict, message_types: dict, message: dict) -> str:
        """Sign an EIP-712 typed data payload with the wallet private key.

        Returns the hex-encoded signature (0x-prefixed).
        Raises ``RuntimeError`` if tier < WALLET.
        """
        ...

    def sign_hash(self, message_hash: bytes) -> str:
        """Sign an arbitrary hash with the wallet private key.

        Used for on-chain contract interactions.
        Raises ``RuntimeError`` if tier < WALLET.
        """
        ...

    # ─── API key management ──────────────────────────────────────────────

    def derive_api_key(self, host: str) -> ApiKeyCredentials:
        """Derive (or re-derive) API key credentials from the wallet.

        This wraps the SDK's ``ClobClient.create_or_derive_api_creds``
        flow.  Raises ``RuntimeError`` if tier < WALLET (API key derivation
        requires the wallet).
        """
        ...

    @property
    def can_sign(self) -> bool:
        """True if this signer can perform EIP-712 signing (tier >= WALLET)."""
        return self.tier == AuthTier.WALLET

    @property
    def can_authenticate(self) -> bool:
        """True if this signer can authenticate to L2 endpoints (tier >= API_KEY)."""
        return self.tier in (AuthTier.API_KEY, AuthTier.WALLET)
```

### 3.2 `client.py` — CLOB REST adapter

**File:** `polymind/polymarket/client.py`

Wraps `py_clob_client.client.ClobClient` for all CLOB REST operations.
Returns domain types from `polymind.core.*` (or dedicated domain types defined
in this module for Polymarket-specific concepts that have no core equivalent).

```python
"""Polymarket CLOB REST adapter.

Translates between py-clob-client SDK types and polymind.core domain types.
All methods are async; synchronous SDK calls are dispatched via executor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from polymind.polymarket.metrics import AdapterMetrics
from polymind.polymarket.signer import Signer


# ── Domain types (Polymarket-specific, no core equivalent) ──────────────


@dataclass
class MarketSummary:
    """Summary of a Polymarket CLOB market."""

    market_id: str
    condition_id: str
    token_id: str           # ERC-1155 token ID for this outcome
    outcome: str            # "YES" or "NO"
    price: float            # current last-trade or midpoint price
    volume_24h: float
    liquidity: float
    open_interest: float
    tick_size: float
    min_size: float
    neg_risk: bool          # True if this is a negative-risk market
    closed: bool
    created_at: datetime


@dataclass
class OrderBookLevel:
    """A single price level in the order book."""

    price: float
    size: float
    num_orders: int


@dataclass
class OrderBookSnapshot:
    """Full order book snapshot for a token."""

    market_id: str
    token_id: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime
    tick_size: float
    min_order_size: str


@dataclass
class OrderResult:
    """Result of placing or cancelling an order."""

    order_id: str
    status: str               # "OPEN", "FILLED", "CANCELLED", "FAILED"
    market_id: str
    side: str                 # "BUY" or "SELL"
    price: str
    size: str
    filled_size: str
    remaining_size: str
    created_at: datetime
    error: Optional[str] = None


# ── Adapter class ───────────────────────────────────────────────────────


class PolymarketClient:
    """Async adapter for the Polymarket CLOB REST API.

    Wraps ``ClobClient`` from ``py-clob-client``.  All public methods accept
    and return domain types; SDK types are never exposed.

    Parameters
    ----------
    host : str
        Polymarket CLOB API host (e.g. ``https://clob.polymarket.com``).
    signer : Signer
        Authentication credentials (public, API key, or wallet).
    chain_id : int, optional
        Polygon chain ID (137 for mainnet, 80002 for amoy). Derived from
        host if omitted.
    metrics : AdapterMetrics, optional
        Metrics collector.  A new instance is created if omitted.
    """

    def __init__(
        self,
        host: str,
        signer: Signer,
        chain_id: Optional[int] = None,
        metrics: Optional[AdapterMetrics] = None,
    ):
        self._host = host
        self._signer = signer
        self._chain_id = chain_id or self._resolve_chain_id(host)
        self._metrics = metrics or AdapterMetrics("polymarket.client")
        self._client: Optional["ClobClient"] = None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Instantiate the underlying ClobClient and authenticate.

        For API-key-tier signers, this derives API credentials if needed
        and sets them on the SDK client.  For public-tier signers, only
        the host and chain ID are configured.

        Safe to call multiple times — subsequent calls are no-ops if
        already connected.
        """
        ...

    async def close(self) -> None:
        """Close the underlying client and release HTTP resources."""
        ...

    # ── Market data ──────────────────────────────────────────────────────

    async def get_markets(self, active: bool = True, limit: int = 50) -> List[MarketSummary]:
        """Fetch active (or all) markets.

        Parameters
        ----------
        active : bool
            If True (default), return only markets that are not closed.
        limit : int
            Maximum number of markets to return (pagination uses cursors
            internally).

        Returns
        -------
        List[MarketSummary]
            One entry per outcome token (two entries per binary market:
            YES and NO).
        """
        ...

    async def get_market(self, market_id: str) -> Optional[MarketSummary]:
        """Fetch a single market by its CLOB market ID."""
        ...

    async def get_order_book(
        self, token_id: str, depth: Optional[int] = None
    ) -> Optional[OrderBookSnapshot]:
        """Fetch the current order book for a token.

        Parameters
        ----------
        token_id : str
            ERC-1155 token ID for the outcome.
        depth : int, optional
            Number of price levels per side.  The SDK default is used if
            omitted.

        Returns
        -------
        OrderBookSnapshot or None
            None if the token ID is unknown or the market is closed.
        """
        ...

    async def get_midpoint(self, token_id: str) -> Optional[float]:
        """Fetch the midpoint price for a token."""
        ...

    async def get_spread(self, token_id: str) -> Optional[float]:
        """Fetch the current bid-ask spread for a token."""
        ...

    async def get_last_trade_price(self, token_id: str) -> Optional[float]:
        """Fetch the last traded price for a token."""
        ...

    @staticmethod
    def _resolve_chain_id(host: str) -> int:
        """Map known hosts to chain IDs."""
        if "amoy" in host.lower():
            return 80002
        return 137

    # ── Orders ────────────────────────────────────────────────────────────

    async def place_order(
        self,
        market_id: str,
        token_id: str,
        side: str,
        price: float,
        size: float,
        order_type: str = "GTC",
        reduce_only: bool = False,
        post_only: bool = True,
        **kwargs,
    ) -> OrderResult:
        """Place a limit order on the CLOB.

        Requires ``signer.can_authenticate == True``.  Raises
        ``PermissionError`` for public-tier signers.

        Returns
        -------
        OrderResult
            Contains the exchange order ID and initial status.
        """
        ...

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a single open order by exchange order ID.

        Returns True if the cancellation was accepted by the exchange.
        """
        ...

    async def cancel_all_orders(self, market_id: Optional[str] = None) -> int:
        """Cancel all open orders, optionally filtered by market.

        Returns the number of cancellation requests sent (not necessarily
        the number of orders actually cancelled — use ``get_orders`` to
        verify).
        """
        ...

    async def get_orders(
        self,
        market_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[OrderResult]:
        """Fetch open (or all) orders, optionally filtered.

        Parameters
        ----------
        market_id : str, optional
            Filter to a specific market.
        status : str, optional
            Filter by status: "OPEN", "FILLED", "CANCELLED", etc.

        Returns
        -------
        List[OrderResult]
        """
        ...

    # ── Account ──────────────────────────────────────────────────────────

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Fetch current positions from the CLOB API.

        Returns a list of position dicts with keys: market_id, token_id,
        outcome, size, avg_price, realized_pnl, unrealized_pnl.

        Note: These are CLOB-reported positions, not on-chain balances.
        On-chain reconciliation (ADR 0003) is handled by ``contracts.py``.
        """
        ...

    async def get_balance(self) -> float:
        """Fetch the USDC balance reported by the CLOB API.

        This is the exchange-managed balance, not the on-chain wallet
        balance.  On-chain balance reads are in ``contracts.py``.
        """
        ...

    # ── Internal helpers ─────────────────────────────────────────────────

    def _map_market(self, raw: Any) -> MarketSummary:
        """Map a raw SDK market response to a domain MarketSummary."""
        ...

    def _map_order_book(self, raw: Any) -> OrderBookSnapshot:
        """Map a raw SDK OrderBookSummary to a domain OrderBookSnapshot."""
        ...

    def _map_order_result(self, raw: Any) -> OrderResult:
        """Map a raw SDK order response to a domain OrderResult."""
        ...
```

### 3.3 `data_api.py` — Data API (metadata, price history, candles)

**File:** `polymind/polymarket/data_api.py`

Provides access to Polymarket's Gamma/Data API endpoints for historical data
used by factors and backtesting. This module is read-only (no order placement).

```python
"""Polymarket Data API adapter.

Read-only access to market metadata, price history, and OHLCV candles.
Returns domain types usable by the factor engine and backtester.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from polymind.polymarket.metrics import AdapterMetrics


@dataclass
class Candle:
    """OHLCV candle for a market outcome."""

    token_id: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    complete: bool            # True if the candle is fully formed


@dataclass
class MarketMetadata:
    """Full metadata for a Polymarket event/market."""

    market_id: str
    condition_id: str
    question: str             # e.g. "Will BTC reach $100k by Dec 2026?"
    description: str
    outcomes: List[str]       # ["YES", "NO"] for binary markets
    token_ids: List[str]      # one per outcome, same order as outcomes
    tick_size: float
    min_size: float
    volume_24h: float
    open_interest: float
    end_date: datetime
    neg_risk: bool
    closed: bool


@dataclass
class Trade:
    """A single CLOB trade (fill) from the Data API."""

    trade_id: str
    market_id: str
    token_id: str
    side: str                  # "BUY" or "SELL"
    price: float
    size: float
    timestamp: datetime
    taker: bool                # True if this was a taker fill


class DataApiClient:
    """Async adapter for Polymarket's Data API.

    Provides market metadata, price history, and trade data for factor
    computation and backtesting.  All calls are read-only and can be made
    without authentication (public tier).

    Parameters
    ----------
    base_url : str
        Data API base URL (e.g. ``https://data.polymarket.com`` or
        ``https://gamma-api.polymarket.com``).
    metrics : AdapterMetrics, optional
    """

    def __init__(
        self,
        base_url: str = "https://gamma-api.polymarket.com",
        metrics: Optional[AdapterMetrics] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._metrics = metrics or AdapterMetrics("polymarket.data_api")
        self._session: Optional["httpx.AsyncClient"] = None

    async def connect(self) -> None:
        """Create the HTTP client session."""
        ...

    async def close(self) -> None:
        """Close the HTTP session."""
        ...

    # ── Market metadata ─────────────────────────────────────────────────

    async def get_market_metadata(self, market_id: str) -> Optional[MarketMetadata]:
        """Fetch full metadata for a single market/event."""
        ...

    async def list_markets(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MarketMetadata]:
        """List available markets with optional filtering.

        Supports pagination via limit/offset.
        """
        ...

    # ── Price history ───────────────────────────────────────────────────

    async def get_candles(
        self,
        token_id: str,
        interval: str = "1h",          # "1h", "4h", "1d", "7d"
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[Candle]:
        """Fetch OHLCV candles for a token.

        The interval parameter follows the Polymarket Data API convention.
        Returns candles sorted by timestamp ascending.

        This is the primary data source for factor signal computation and
        backtesting.
        """
        ...

    async def get_price_history(
        self,
        token_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Trade]:
        """Fetch historical trades/fills for a token.

        Useful for reconstructing order book dynamics off-line.
        """
        ...

    # ── Trades ──────────────────────────────────────────────────────────

    async def get_recent_trades(
        self,
        token_id: str,
        limit: int = 100,
    ) -> List[Trade]:
        """Fetch the most recent trades for a token.

        This is a lightweight alternative to get_price_history when only
        recent activity is needed.
        """
        ...

    # ── Internal helpers ────────────────────────────────────────────────

    def _map_candle(self, raw: dict) -> Candle:
        """Map a raw Data API candle response to domain Candle."""
        ...

    def _map_metadata(self, raw: dict) -> MarketMetadata:
        """Map a raw Data API market response to domain MarketMetadata."""
        ...

    def _map_trade(self, raw: dict) -> Trade:
        """Map a raw Data API trade response to domain Trade."""
        ...
```

### 3.4 `websocket.py` — Public and authenticated WebSocket streams

**File:** `polymind/polymarket/websocket.py`

Manages asyncio-based WebSocket connections to Polymarket's public and
authenticated streams. Reconnection uses exponential backoff. WebSocket events
are emitted as callbacks (not business logic sinks — see ADR 0003).

```python
"""Polymarket WebSocket adapter.

Manages asyncio WebSocket connections with automatic reconnection.
Events are dispatched to registered callbacks.  No business logic runs
inside callbacks — they are wake-up signals only (ADR 0003).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set

from polymind.polymarket.signer import Signer


# ── Channel types ──────────────────────────────────────────────────────


class ChannelType(Enum):
    """WebSocket channel categories."""

    ORDER_BOOK = "orderbook"           # public: bid/ask snapshots and deltas
    TRADES = "trades"                  # public: fill events
    TICKER = "ticker"                  # public: price/ticker updates
    USER_FILLS = "user"                # authenticated: user-specific fills
    USER_ORDERS = "user"               # authenticated: order status changes
    USER_POSITIONS = "user"            # authenticated: position changes


# ── Event types ────────────────────────────────────────────────────────


@dataclass
class OrderBookEvent:
    """WebSocket order-book delta or snapshot event."""

    market_id: str
    token_id: str
    bids: List[Dict[str, str]]         # [{price: str, size: str}, ...]
    asks: List[Dict[str, str]]
    timestamp: datetime
    is_snapshot: bool                  # True = full refresh, False = delta


@dataclass
class TradeEvent:
    """WebSocket trade/fill event (public channel)."""

    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    trade_id: str
    timestamp: datetime


@dataclass
class TickerEvent:
    """WebSocket ticker/price-update event."""

    market_id: str
    token_id: str
    price: float
    volume_24h: float
    timestamp: datetime


@dataclass
class UserFillEvent:
    """WebSocket user-specific fill event (authenticated channel).

    This is the primary low-latency wake-up signal for the reconciliation
    layer (ADR 0003).  It is NOT the source of truth — on-chain balance
    reads serve that role.
    """

    order_id: str
    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    fee: float
    trade_id: str
    timestamp: datetime


# ── Connection config ─────────────────────────────────────────────────


@dataclass
class WebSocketConfig:
    """Configuration for WebSocket connections."""

    max_retries: int = 10
    base_retry_delay: float = 1.0      # seconds, doubled each attempt
    max_retry_delay: float = 60.0
    ping_interval: float = 20.0        # seconds
    ping_timeout: float = 10.0


# ── Callback types ────────────────────────────────────────────────────


OrderBookCallback = Callable[[OrderBookEvent], None]
TradeCallback = Callable[[TradeEvent], None]
TickerCallback = Callable[[TickerEvent], None]
UserFillCallback = Callable[[UserFillEvent], None]


# ── Manager class ──────────────────────────────────────────────────────


class WebSocketManager:
    """Manages asyncio WebSocket connections to Polymarket.

    Supports multiple concurrent subscriptions (channels).  Reconnection
    is handled internally with exponential backoff.  Events are dispatched
    to registered callbacks.

    The manager does NOT run business logic.  Callbacks must be fast and
    non-blocking — they should enqueue work for the reconciliation or
    executor layer, not perform I/O themselves.

    Parameters
    ----------
    ws_url : str
        WebSocket endpoint (e.g. ``wss://ws-subscriptions-clob.polymarket.com/ws/``).
    signer : Signer, optional
        If provided with tier >= API_KEY, authenticated channels are available.
    config : WebSocketConfig, optional
        Reconnection and keepalive settings.
    """

    def __init__(
        self,
        ws_url: str,
        signer: Optional[Signer] = None,
        config: Optional[WebSocketConfig] = None,
    ):
        self._ws_url = ws_url
        self._signer = signer
        self._config = config or WebSocketConfig()
        self._subscriptions: Set[ChannelType] = set()
        self._callbacks: Dict[ChannelType, List[Callable]] = {}
        self._task: Optional["asyncio.Task"] = None
        self._connected: bool = False

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Start the WebSocket connection and event loop.

        Launches a background asyncio task that manages the connection
        lifecycle.  This method returns once the initial handshake is
        complete or raises if the first connection fails.
        """
        ...

    async def disconnect(self) -> None:
        """Gracefully close the WebSocket and stop the reconnect loop."""
        ...

    async def subscribe(
        self,
        channel: ChannelType,
        assets: Optional[List[str]] = None,
        callback: Optional[Callable] = None,
    ) -> None:
        """Subscribe to a channel.

        Parameters
        ----------
        channel : ChannelType
            The channel to subscribe to.
        assets : list of str, optional
            Token IDs or market IDs to filter (None = subscribe to all).
        callback : callable, optional
            Function to call on each event.  If not provided, events can
            be polled via ``poll_events()``.

        Raises
        ------
        PermissionError
            If the channel requires authentication and the signer's tier
            is insufficient.
        RuntimeError
            If called before ``connect()``.
        """
        ...

    async def unsubscribe(
        self,
        channel: ChannelType,
        assets: Optional[List[str]] = None,
    ) -> None:
        """Unsubscribe from a channel (or specific assets on it)."""
        ...

    # ── Event polling (alternative to callbacks) ───────────────────────

    def poll_events(self, channel: ChannelType, max_count: int = 10) -> List[Any]:
        """Dequeue buffered events for a channel.

        Returns up to ``max_count`` events that have arrived since the
        last poll.  Returns an empty list immediately if no events are
        buffered.

        This is the recommended interface for the reconciliation loop:
        polls on a timer rather than reacting to every WebSocket message.
        """
        ...

    # ── Status ─────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """True if the WebSocket is currently connected."""
        return self._connected

    @property
    def active_subscriptions(self) -> List[ChannelType]:
        """Return the list of currently subscribed channels."""
        ...

    # ── Internal ───────────────────────────────────────────────────────

    async def _connection_loop(self) -> None:
        """Background task: maintain connection and dispatch events.

        Implements exponential backoff reconnection on disconnect.
        """
        ...

    async def _handle_message(self, raw: dict) -> None:
        """Deserialize a raw WebSocket message and dispatch to callbacks."""
        ...

    async def _send_subscription(self, channel: ChannelType, assets: List[str]) -> None:
        """Send a subscription message on the active WebSocket."""
        ...
```

### 3.5 `contracts.py` — On-chain contract operations

**File:** `polymind/polymarket/contracts.py`

Wraps on-chain interactions via Web3.py: ERC-1155 operations (split, merge,
redeem), collateral approvals, and CTF exchange operations. All methods
require a wallet-tier signer.

```python
"""Polymarket on-chain contract adapter.

ERC-1155 operations, collateral management, and CTF exchange interactions.
All methods require wallet-tier authentication (Signer.tier >= WALLET).

These are the reconciliation source of truth (ADR 0003) — on-chain balances
supersede CLOB-reported positions and WebSocket fill events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Optional

from polymind.polymarket.metrics import AdapterMetrics
from polymind.polymarket.signer import Signer


@dataclass
class OnChainBalance:
    """ERC-1155 token balance and USDC balance on-chain."""

    token_id: str
    balance: int               # raw ERC-1155 balance (may be fractional)
    usdc_balance: float        # USDC collateral balance
    decimals: int = 6


@dataclass
class TransactionResult:
    """Outcome of an on-chain transaction."""

    tx_hash: str
    status: str                # "PENDING", "CONFIRMED", "FAILED"
    block_number: int
    gas_used: int
    gas_price_gwei: float


class ContractClient:
    """Async adapter for Polymarket on-chain contract interactions.

    Uses Web3.py to interact with Polygon.  All methods are async and
    submit transactions via ``eth_sendRawTransaction`` (locally signed
    using the wallet private key).

    Parameters
    ----------
    rpc_url : str
        Polygon RPC endpoint (e.g. ``https://polygon-rpc.com`` or an
        Alchemy/Infura endpoint).
    signer : Signer
        Must be wallet-tier (signer.can_sign == True).
    chain_id : int
        Polygon chain ID (137 or 80002).
    metrics : AdapterMetrics, optional
    """

    def __init__(
        self,
        rpc_url: str,
        signer: Signer,
        chain_id: int = 137,
        metrics: Optional[AdapterMetrics] = None,
    ):
        self._rpc_url = rpc_url
        self._signer = signer
        self._chain_id = chain_id
        self._metrics = metrics or AdapterMetrics("polymarket.contracts")
        self._w3: Optional["Web3"] = None
        self._contracts: dict = {}       # cached contract instances

    async def connect(self) -> None:
        """Initialize Web3 connection and cache contract instances."""
        ...

    async def close(self) -> None:
        """Disconnect and release resources."""
        ...

    # ── Balance reads (ADR 0003 reconciliation truth) ──────────────────

    async def get_onchain_balance(self, token_id: str) -> OnChainBalance:
        """Read ERC-1155 token balance and USDC balance on-chain.

        This is the reconciliation source of truth.  Always prefer this
        over CLOB-reported positions for final position verification.
        """
        ...

    # ── ERC-1155 operations ────────────────────────────────────────────

    async def split(
        self,
        condition_id: str,
        collateral_amount: int,        # amount of USDC to split
        outcomes: list,
    ) -> TransactionResult:
        """Split USDC collateral into YES/NO outcome tokens.

        Requires prior USDC approval for the CTF exchange.
        """
        ...

    async def merge(
        self,
        condition_id: str,
        amount: int,
        outcomes: list,
    ) -> TransactionResult:
        """Merge YES/NO tokens back into USDC collateral.

        Both YES and NO tokens must be held in equal quantities.
        """
        ...

    async def redeem(
        self,
        condition_id: str,
        outcome_index: int,
        amount: int,
    ) -> TransactionResult:
        """Redeem winning tokens for USDC after market resolution.

        Only the winning outcome can be redeemed.  The transaction
        fails if the market has not been resolved.
        """
        ...

    # ── Approvals ──────────────────────────────────────────────────────

    async def approve_usdc(self, amount: int) -> TransactionResult:
        """Approve the CTF exchange to spend USDC.

        Required before split/merge operations.  ``amount`` is the
        maximum approval (set to ``2**256-1`` for unlimited).
        """
        ...

    async def approve_exchange(self, token_id: str, amount: int) -> TransactionResult:
        """Approve the CTF exchange to transfer an ERC-1155 token.

        Required before placing orders on the CLOB for this token.
        """
        ...

    # ── Internal helpers ────────────────────────────────────────────────

    def _get_contract(self, name: str, address: str, abi: list) -> Any:
        """Get or create a cached Web3 contract instance."""
        ...

    async def _send_transaction(self, tx: dict) -> TransactionResult:
        """Sign, send, and wait for a transaction.

        Signs locally using the wallet private key, sends via
        ``eth_sendRawTransaction``, and waits for confirmation.
        """
        ...
```

### 3.6 `metrics.py` — Adapter instrumentation

**File:** `polymind/polymarket/metrics.py`

Prometheus-compatible counters and histograms for monitoring adapter health.
Exported as a single class used by all other adapter modules.

```python
"""Adapter instrumentation — Prometheus counters and histograms."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Counter:
    """Simple monotonic counter (Prometheus Counter equivalent)."""

    name: str
    labels: Dict[str, str] = field(default_factory=dict)
    _value: int = 0

    def inc(self, amount: int = 1) -> None:
        self._value += amount

    @property
    def value(self) -> int:
        return self._value


@dataclass
class Histogram:
    """Simple histogram for latency distributions.

    Buckets follow Prometheus defaults: [0.005, 0.01, 0.025, 0.05, 0.1,
    0.25, 0.5, 1.0, 2.5, 5.0, 10.0] seconds.
    """

    name: str
    labels: Dict[str, str] = field(default_factory=dict)
    _buckets: tuple = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    _counts: Dict[float, int] = field(default_factory=dict)
    _sum: float = 0.0

    def observe(self, value: float) -> None:
        """Record an observation.

        ``value`` is typically a duration in seconds.
        """
        self._sum += value
        for bucket in self._buckets:
            if value <= bucket:
                ...

    @property
    def count(self) -> int:
        ...

    @property
    def sum(self) -> float:
        ...


class AdapterMetrics:
    """Collector for adapter-level metrics.

    Usage::

        metrics = AdapterMetrics("polymarket.client")
        metrics.calls_total.inc()
        with metrics.latency_seconds.time():
            result = await do_something()

    Each adapter module creates its own instance with a unique prefix.
    """

    def __init__(self, prefix: str):
        self.prefix = prefix

        # ── Call-level counters ────────────────────────────────────────
        self.calls_total: Counter = Counter(f"{prefix}_calls_total")
        self.errors_total: Counter = Counter(f"{prefix}_errors_total")
        self.retries_total: Counter = Counter(f"{prefix}_retries_total")

        # ── Latency histogram ──────────────────────────────────────────
        self.latency_seconds: Histogram = Histogram(f"{prefix}_latency_seconds")

        # ── WebSocket-specific ─────────────────────────────────────────
        self.ws_disconnects_total: Counter = Counter(f"{prefix}_ws_disconnects_total")
        self.ws_reconnects_total: Counter = Counter(f"{prefix}_ws_reconnects_total")
        self.ws_messages_received: Counter = Counter(f"{prefix}_ws_messages_received")

    @contextmanager
    def measure(self) -> None:
        """Context manager that records call duration as a histogram.

        If the body raises, ``errors_total`` is incremented automatically.
        """
        import time

        start = time.monotonic()
        try:
            yield
        except Exception:
            self.errors_total.inc()
            raise
        finally:
            self.latency_seconds.observe(time.monotonic() - start)
            self.calls_total.inc()
```

## 4. Error Handling Patterns

All adapter modules follow a consistent error handling strategy:

### 4.1 Exception Hierarchy

```python
class PolymarketAdapterError(Exception):
    """Base for all adapter-level errors."""
    ...


class AuthenticationError(PolymarketAdapterError):
    """Raised when API key or wallet credentials are invalid/expired."""
    ...


class InsufficientAuthError(PolymarketAdapterError):
    """Raised when an operation requires a higher auth tier."""
    ...


class MarketNotFoundError(PolymarketAdapterError):
    """Raised when a requested market/token does not exist."""
    ...


class OrderRejectedError(PolymarketAdapterError):
    """Raised when the CLOB rejects an order (invalid price, size, etc.)."""
    ...


class RateLimitError(PolymarketAdapterError):
    """Raised on HTTP 429 from the CLOB API or Data API."""

    retry_after: float          # seconds suggested by the server


class ConnectionError(PolymarketAdapterError):
    """Raised on network-level failures (DNS, timeout, connection refused)."""
    ...


class WebSocketDisconnect(PolymarketAdapterError):
    """Raised internally by WebSocketManager on unexpected disconnect.

    Not exposed to callers — the reconnection loop handles it.
    """
    ...


class ContractError(PolymarketAdapterError):
    """Raised when an on-chain transaction reverts or fails."""
    ...


class NonceTooLowError(ContractError):
    """Raised when a transaction nonce is too low (stale nonce)."""
    ...


class InsufficientGasError(ContractError):
    """Raised when the wallet lacks MATIC for gas."""
    ...
```

### 4.2 Error Handling Rules

1. **SDK exceptions are caught and re-raised as adapter exceptions.** No
   `py_clob_client.exceptions.PolyApiException` leaks to callers.
2. **Transient errors** (network timeouts, HTTP 5xx, rate limits) are retried
   with exponential backoff via `tenacity` (already a dependency). Retries are
   configurable per adapter.
3. **Permanent errors** (HTTP 4xx except 429, invalid credentials) are raised
   immediately with a descriptive message.
4. **WebSocket disconnects** are handled internally by `WebSocketManager`.
   Callback code runs in a try/except — if a callback raises, the error is
   logged and the callback is removed from the dispatch list.
5. **On-chain transaction failures** (reverts, out-of-gas) are caught and
   returned as `TransactionResult(status="FAILED")` rather than raised, so the
   caller can decide on retry strategy.

## 5. Auth Patterns

### 5.1 Auth Tier Mapping

| Auth Tier | Signer Factory | Available Operations | Adapters |
|---|---|---|---|
| PUBLIC | `Signer.public()` | Market data, order books, tickers, Data API | `client.py` (read), `data_api.py`, `websocket.py` (public channels) |
| API_KEY | `Signer.from_api_key(key, secret, pass)` | + order placement/cancellation, user WebSocket | `client.py` (write), `websocket.py` (user channels) |
| WALLET | `Signer.from_wallet(pk)` | + on-chain operations, API key derivation | `contracts.py`, `signer.py` (key derivation) |

### 5.2 Credential Lifecycle

1. **Startup**: The `Signer` is constructed from config (env vars, config file,
   or vault). A wallet-tier signer can derive API keys on first use.
2. **Connection**: `PolymarketClient.connect()` calls `ClobClient.set_api_creds`
   if the signer has API key credentials. For wallet-tier signers, API keys
   are derived automatically if not already present.
3. **Runtime**: The `Signer` is immutable and shared across adapter instances.
   No module mutates credentials after initialization.
4. **Rotation**: Credential rotation requires restarting the adapter instances.
   Hot-reload is a future concern.

### 5.3 Security Constraints

- Private keys are held in `Signer.wallet_creds` and are **never logged or
  exposed in error messages**.
- API keys and secrets are similarly masked in string representations.
- The `Signer` class implements `__repr__` to show only the auth tier and a
  truncated address (wallet tier) or prefix of the API key.
- `contracts.py` signs transactions locally — the private key never leaves
  the process.

## 6. Integration Points With Existing Code

### 6.1 Core domain types consumed by adapters

| Core type (File) | Used by | Direction |
|---|---|---|
| `StrategyIntent` (`core/intents.py`) | `client.place_order()` maps OrderIntent to SDK order args | Core -> Adapter |
| `FillEvent` (`core/fills.py`) | Adapters produce FillEvents from WebSocket events and CLOB polls | Adapter -> Core |
| `LedgerEntry` (`core/ledger.py`) | Adapters (via executor) record ledger entries after fills | Adapter -> Core |
| `OrderSide` (`core/intents.py`) | Adapters map BUY/SELL to SDK side strings | Core -> Adapter |
| `PortfolioTarget` (`core/portfolio.py`) | Not directly used by adapters; converted to intents by bridge layer | (Future) |

### 6.2 How the adapter layer is called

The adapter layer is consumed by the execution layer (Phase 3) and
reconciliation layer (Phase 5):

```
StrategyIntent
      |
      v
  RiskGates  (Phase 2 - core/risk.py)
      |
      v
  IntentExecutor (abstract - core/intents.py)
      |
      +-- PaperExecutor (Phase 3 - executes in memory)
      |
      +-- LiveExecutor (Future - uses PolymarketClient)
              |
              +-- PolymarketClient.place_order()     [client.py]
              +-- PolymarketClient.cancel_order()    [client.py]
              +-- WebSocketManager.poll_events()     [websocket.py]
              +-- ContractClient.get_onchain_balance() [contracts.py]
              +-- DataApiClient.get_candles()        [data_api.py]
```

### 6.3 Fill detection flow (ADR 0003)

```
1. WebSocket event arrives        (websocket.py -> UserFillEvent)
2. Enqueues reconciliation task   (core/workflows.py)
3. CLOB REST cross-check          (client.py -> get_orders)
4. On-chain balance verification  (contracts.py -> get_onchain_balance)
5. FillEvent produced             (core/fills.py)
6. LedgerEntry recorded           (core/ledger.py)
```

Steps 2-6 are orchestrated by the reconciliation layer (Phase 5), not by the
adapters themselves. The adapters provide the raw data.

### 6.4 Data flow for factors/backtesting

```
DataApiClient.get_candles()       (data_api.py)
        |
        v
  Candle domain objects
        |
        v
  Factor signal computation        (polymind/factors/)
        |
        v
  PortfolioTarget                  (core/portfolio.py)
        |
        v
  StrategyIntent                   (core/intents.py)
        |
        v
  Executor                         (paper or live)
```

### 6.5 Connection ownership

The `PolymarketClient`, `WebSocketManager`, `DataApiClient`, and
`ContractClient` are independent connection pools. In a typical deployment,
they are created once and injected into the executor:

```python
# Application wiring (conceptual, not part of this spec)
signer = Signer.from_wallet(config.private_key)

clob = PolymarketClient(host=config.clob_host, signer=signer)
ws = WebSocketManager(ws_url=config.ws_url, signer=signer)
data = DataApiClient()
contracts = ContractClient(rpc_url=config.rpc_url, signer=signer, chain_id=config.chain_id)

await clob.connect()
await ws.connect()
await data.connect()
await contracts.connect()

executor = LiveExecutor(clob=clob, ws=ws, contracts=contracts)
```

### 6.6 Existing stub compatibility

The existing `PolymarketClient` stub in `polymind/polymarket/client.py` has
seven methods that return trivial defaults. The implementation in this spec
preserves all seven method names (`get_markets`, `get_positions`,
`get_balance`, `place_order`, `cancel_order`, `cancel_all_orders`, `close`)
while adding:

- Rich return types instead of `[]`, `0.0`, `True`, `None`
- `connect()` for explicit initialization
- `get_market()`, `get_order_book()`, `get_midpoint()`, `get_spread()`,
  `get_last_trade_price()`, `get_orders()` — additional endpoints
- `signer` and `metrics` constructor parameters
- Full SDK integration via `ClobClient`

The `__init__.py` remains unchanged (it already exports `PolymarketClient`).

## 7. Test Plan

| Test file | Tests |
|---|---|
| `tests/polymarket/test_signer.py` | AuthTier enum values, Signer factory methods (public, from_api_key, from_wallet), credential access, tier checks (can_sign, can_authenticate), __repr__ key masking, derive_api_key raises for non-wallet, sign_typed_data requires WALLET tier |
| `tests/polymarket/test_client.py` | (Existing file — expand) Constructor with/without signer, connect initializes ClobClient, get_markets returns MarketSummary list, get_market returns single or None, get_order_book returns OrderBookSnapshot, get_midpoint/get_spread/get_last_trade_price return floats or None, place_order requires auth, cancel_order returns bool, cancel_all_orders returns count, get_orders returns list, get_positions/get_balance return data, close releases client, error mapping from SDK exceptions, retry on transient failure |
| `tests/polymarket/test_data_api.py` | DataApiClient connect/close lifecycle, get_market_metadata returns MarketMetadata, list_markets supports pagination, get_candles returns Candle list sorted by timestamp, interval parameter validation, get_price_history returns Trade list, get_recent_trades limit works, error handling for HTTP errors, rate limit handling |
| `tests/polymarket/test_websocket.py` | WebSocketManager connect/disconnect lifecycle, subscribe to public channels (ORDER_BOOK, TRADES, TICKER), subscribe to authenticated channels requires signer, callback dispatch for each event type, poll_events returns buffered events, unsubscribe removes subscription, reconnection on disconnect, exponential backoff delays, max retries exceeded raises, graceful shutdown via disconnect |
| `tests/polymarket/test_contracts.py` | ContractClient connect initializes Web3, signer must be wallet tier, get_onchain_balance returns OnChainBalance, split/merge/redeem produce TransactionResult, approve_usdc and approve_exchange produce TransactionResult, transaction failure returns FAILED status, nonce too low handled, gas estimation errors caught |
| `tests/polymarket/test_metrics.py` | Counter inc and value, Histogram observe and bucket counts, AdapterMetrics prefixes, measure context manager records latency and increments errors on exception |
| `tests/polymarket/test_error_handling.py` | All exception types construct and stringify correctly, error mapping from SDK PolyApiException to adapter types, InsufficientAuthError raised for mismatched tier operations, RateLimitError includes retry_after, transient errors retry via tenacity |
| `tests/polymarket/test_integration_client_data.py` | PolymarketClient + DataApiClient: get_market_metadata returns same market_id as get_markets, token_ids from metadata match order book queries (mock-based, no live network) |

### 7.1 Testing approach

- **Unit tests** mock the SDK classes (`ClobClient`, `Web3`) at the adapter
  boundary. Adapter methods are tested with controlled SDK return values.
- **No live network calls** in CI. All tests use `unittest.mock` or pytest
  fixtures with fake HTTP responses.
- **WebSocket tests** use a mock WebSocket server (via `asyncio` streams) to
  verify reconnection, subscription messages, and event dispatch without
  touching the real Polymarket endpoint.
- **Contract tests** mock `Web3` to return canned transaction receipts and
  balance data. No RPC calls.
- **Integration tests** (single marked as `pytest.mark.integration`) verify
  cross-adapter consistency with mocked SDK responses.

## 8. Future Extensions (not in this spec)

- **Builder attribution** — `client.py` will gain `set_builder_fee` and
  builder-aware order placement when the feature is needed.
- **RFQ (Request-for-Quote)** — an RFQ adapter for large-block trades, wrapping
  `py_clob_client.rfq`.
- **Hot credential reload** — the `Signer` could be replaced at runtime for
  credential rotation without restart.
- **SQLite/duckdb persistence** for Data API candle caching to reduce API calls
  in backtesting.
- **Full reconciliation layer** (Phase 5) — the workflow that wires WebSocket
  events -> CLOB cross-check -> on-chain verification -> FillEvent.
- **py-clob-client-v2 migration** — when the unified SDK is stable, only these
  adapter modules change; core strategy code is unaffected (per ADR 0004).
