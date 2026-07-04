"""
Polymarket CLOB API client.

Wraps py-clob-client for order management, market data, and balance.
All public methods are async and use asyncio.to_thread for blocking SDK calls.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OpenOrderParams, OrderArgs, TradeParams
from py_clob_client.exceptions import PolyApiException, PolyException

from polymind.polymarket.errors import (
    ConnectionError as PolymarketConnectionError,
)
from polymind.polymarket.errors import (
    MarketNotFoundError,
    PolymarketError,
    RateLimitError,
)
from polymind.polymarket.metrics import AdapterMetrics
from polymind.polymarket.signer import Signer
from polymind.polymarket.types import OrderBookLevel, OrderBookSnapshot

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class MarketSummary:
    """Simplified market and token summary returned by the CLOB API."""

    market_id: str
    condition_id: str
    token_id: str
    outcome: str
    price: float
    volume_24h: float = 0.0
    liquidity: float = 0.0
    open_interest: float = 0.0
    tick_size: float = 0.01
    min_size: float = 1.0
    neg_risk: bool = False
    closed: bool = False
    created_at: datetime | None = None


@dataclass
class OrderResult:
    """Result of a submitted or fetched order."""

    order_id: str
    status: str
    market_id: str
    side: str
    price: str
    size: str
    filled_size: str
    remaining_size: str
    created_at: datetime
    error: str | None = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class PolymarketClient:
    """Async wrapper around py-clob-client's synchronous ClobClient.

    Uses :func:`asyncio.to_thread` to offload blocking SDK calls and maps
    SDK exceptions to the project's ``PolymarketError`` hierarchy.

    Parameters
    ----------
    host:
        Polymarket CLOB API base URL.
    signer:
        Optional :class:`Signer` holding credentials for the desired auth tier.
        ``None`` means public (read-only, unauthenticated) access.
    chain_id:
        Chain ID (137 = Polygon mainnet, 80001 = Mumbai testnet).  Auto-detected
        from *host* when omitted.
    metrics:
        Optional :class:`AdapterMetrics` instance for instrumentation.
    """

    def __init__(
        self,
        host: str = "https://clob.polymarket.com",
        signer: Signer | None = None,
        chain_id: int | None = None,
        metrics: AdapterMetrics | None = None,
    ):
        self._host = host
        self._signer = signer
        self._chain_id = chain_id or self._resolve_chain_id(host)
        self._metrics = metrics or AdapterMetrics("polymarket.client")
        self._client: ClobClient | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Create the underlying SDK client (idempotent).

        Safe to call multiple times — subsequent calls are no-ops once the
        SDK client has been created.
        """
        if self._client is not None:
            return
        async with self._lock:
            if self._client is not None:
                return
            self._client = self._build_client()

    async def close(self) -> None:
        """Release the underlying SDK client. Idempotent."""
        self._client = None

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    async def get_markets(self, active: bool = True, limit: int = 50) -> list[MarketSummary]:
        """Fetch markets from the CLOB, optionally filtered by *active* status.

        Returns up to *limit* :class:`MarketSummary` objects.  The CLOB API
        returns at most 1 000 markets per page; only the first page is fetched.
        """
        data = await self._run("get_markets")
        raw_list: list[dict] = data if isinstance(data, list) else data.get("data", [])

        results: list[MarketSummary] = []
        for item in raw_list:
            if active and not item.get("active", True):
                continue

            condition_id = item.get("condition_id", "")
            closed = item.get("closed", False)
            tick_size = float(item.get("minimum_tick_size", 0.01))
            min_size = float(item.get("minimum_order_size", 1.0))
            neg_risk = item.get("neg_risk", False)
            created_at = _parse_timestamp(item.get("accepting_order_timestamp"))

            for token in item.get("tokens", []):
                results.append(
                    MarketSummary(
                        market_id=condition_id,
                        condition_id=condition_id,
                        token_id=token.get("token_id", ""),
                        outcome=token.get("outcome", ""),
                        price=float(token.get("price", 0)),
                        tick_size=tick_size,
                        min_size=min_size,
                        neg_risk=neg_risk,
                        closed=closed,
                        created_at=created_at or datetime.now(),
                    )
                )
                if len(results) >= limit:
                    return results
        return results

    async def get_market(self, condition_id: str) -> MarketSummary | None:
        """Fetch a single market by its condition ID.

        Returns ``None`` when the market is not found.
        """
        try:
            data = await self._run("get_market", condition_id)
        except MarketNotFoundError:
            return None
        if not data:
            return None
        return self._parse_market(data)

    # ------------------------------------------------------------------
    # Order book
    # ------------------------------------------------------------------

    async def get_order_book(self, token_id: str) -> OrderBookSnapshot | None:
        """Fetch the current order book for *token_id*.

        Returns ``None`` when no order book exists for the token.
        """
        from py_clob_client.clob_types import OrderBookSummary

        try:
            book: OrderBookSummary = await self._run("get_order_book", token_id)
        except (MarketNotFoundError, PolymarketError):
            return None

        if not book:
            return None

        timestamp = _parse_timestamp(book.timestamp) or datetime.now()
        return OrderBookSnapshot(
            market_id=book.market,
            token_id=book.asset_id,
            bids=[
                OrderBookLevel(price=float(b.price), size=float(b.size)) for b in (book.bids or [])
            ],
            asks=[
                OrderBookLevel(price=float(a.price), size=float(a.size)) for a in (book.asks or [])
            ],
            timestamp=timestamp,
            tick_size=float(book.tick_size) if book.tick_size else 0.01,
            min_order_size=book.min_order_size or "1",
        )

    async def get_midpoint(self, token_id: str) -> float:
        """Fetch the midpoint price for *token_id*.

        Returns ``0.0`` when the market has no order book.
        """
        try:
            return float(await self._run("get_midpoint", token_id))
        except (MarketNotFoundError, PolymarketError):
            return 0.0

    async def get_spread(self, token_id: str) -> float:
        """Fetch the spread for *token_id*.

        Returns ``0.0`` when the market has no order book.
        """
        try:
            return float(await self._run("get_spread", token_id))
        except (MarketNotFoundError, PolymarketError):
            return 0.0

    async def get_last_trade_price(self, token_id: str) -> float:
        """Fetch the last traded price for *token_id*.

        Returns ``0.0`` when no trade has occurred yet.
        """
        try:
            result = await self._run("get_last_trade_price", token_id)
            if isinstance(result, dict):
                return float(result.get("price", 0.0))
            return float(result)
        except (MarketNotFoundError, PolymarketError):
            return 0.0

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    async def get_orders(self, params: dict[str, Any] | None = None) -> list[OrderResult]:
        """Fetch orders for the authenticated account.

        *params* may contain ``market``, ``id``, or ``asset_id`` keys to
        filter results.  Requires API-key or wallet-level auth.

        Returns an empty list on auth errors or API failures.
        """
        open_params = None
        if params:
            open_params = OpenOrderParams(
                market=params.get("market"),
                id=params.get("id"),
                asset_id=params.get("asset_id"),
            )
        try:
            raw_orders = await self._run("get_orders", open_params)
        except PolymarketError:
            return []

        results: list[OrderResult] = []
        for item in raw_orders or []:
            results.append(self._parse_order(item))
        return results

    async def get_order(self, order_id: str) -> OrderResult | None:
        """Fetch a single order by ID.

        Returns ``None`` when the order is not found or on auth errors.
        Requires API-key or wallet-level auth.
        """
        try:
            data = await self._run("get_order", order_id)
        except (MarketNotFoundError, PolymarketError):
            return None
        if not data:
            return None
        return self._parse_order(data)

    async def place_order(self, **kwargs: Any) -> dict | None:
        """Place an order on the CLOB.

        Accepts keyword arguments matching :class:`OrderArgs`:

        - ``token_id`` (str) — required
        - ``price`` (float) — required
        - ``size`` (float) — required
        - ``side`` (str) — required, ``"BUY"`` or ``"SELL"``
        - ``fee_rate_bps`` (int, optional)
        - ``nonce`` (int, optional)
        - ``expiration`` (int, optional)
        - ``taker`` (str, optional)

        Requires wallet-level auth (signing capability).

        Returns the raw SDK response dict on success, or ``None`` on failure.
        """
        order_args = OrderArgs(
            token_id=kwargs.get("token_id", ""),
            price=float(kwargs.get("price", 0.0)),
            size=float(kwargs.get("size", 0.0)),
            side=kwargs.get("side", "BUY"),
            fee_rate_bps=int(kwargs.get("fee_rate_bps", 0)),
            nonce=int(kwargs.get("nonce", 0)),
            expiration=int(kwargs.get("expiration", 0)),
            taker=kwargs.get("taker", "0x0000000000000000000000000000000000000000"),
        )
        try:
            order = await self._run("create_order", order_args)
            result = await self._run("post_order", order)
            return result
        except PolymarketError:
            return None

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a single order by ID.

        Returns ``True`` on acceptance (the SDK cancel call succeeded without
        raising).  Note that the exchange may still reject the cancellation.
        """
        try:
            await self._run("cancel", order_id)
            return True
        except PolymarketError:
            return False

    async def cancel_all_orders(self) -> bool:
        """Cancel all open orders.

        Returns ``True`` on acceptance.
        """
        try:
            await self._run("cancel_all")
            return True
        except PolymarketError:
            return False

    # ------------------------------------------------------------------
    # Portfolio & history
    # ------------------------------------------------------------------

    async def get_positions(self) -> list[Any]:
        """Fetch open positions (stub — not yet implemented via CLOB SDK).

        The CLOB SDK does not expose a dedicated positions endpoint.
        Positions can be derived from trade history and order data.
        """
        return []

    async def get_balance(self) -> float:
        """Fetch USDC balance via the CLOB balance/allowance endpoint.

        Requires API-key or wallet-level auth.  Returns ``0.0`` on failure.
        """
        try:
            data = await self._run("get_balance_allowance")
            if isinstance(data, dict):
                return float(data.get("balance", 0.0))
            return 0.0
        except PolymarketError:
            return 0.0

    async def get_fills(self, market_id: str) -> list[Any]:
        """Fetch fills (trades) for *market_id* via the CLOB API.

        Returns :class:`~polymind.core.fills.FillEvent` objects.
        Requires API-key or wallet-level auth.
        """
        from polymind.core.fills import FillEvent, FillSource
        from polymind.core.intents import OrderSide

        params = TradeParams(market=market_id)
        try:
            raw_trades = await self._run("get_trades", params)
        except PolymarketError:
            return []

        fills: list[FillEvent] = []
        for item in raw_trades or []:
            timestamp = _parse_timestamp(item.get("timestamp") or item.get("t", ""))
            side_raw = (item.get("side", "") or "").upper()
            fills.append(
                FillEvent(
                    fill_id=item.get("id", ""),
                    market_id=market_id,
                    outcome=item.get("outcome", ""),
                    side=OrderSide.BUY if side_raw == "BUY" else OrderSide.SELL,
                    price=float(item.get("price", 0)),
                    size=float(item.get("size", 0)),
                    fee=float(item.get("fee", 0)),
                    timestamp=timestamp or datetime.now(),
                    source=FillSource.CLOB_API,
                    order_id=item.get("order_id"),
                    taker=item.get("taker", False),
                )
            )
        return fills

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_chain_id(host: str) -> int:
        """Resolve the chain ID from the host URL."""
        if "staging" in host or "dev" in host:
            return 80001  # Polygon Mumbai
        return 137  # Polygon Mainnet

    def _build_client(self) -> ClobClient:
        """Construct the underlying SDK client based on signer credentials."""
        if self._signer and self._signer.wallet_creds:
            client = ClobClient(
                host=self._host,
                chain_id=self._chain_id,
                key=self._signer.wallet_creds.private_key,
            )
        elif self._signer and self._signer.api_creds:
            client = ClobClient(host=self._host, chain_id=self._chain_id)
            client.set_api_creds(
                ApiCreds(
                    api_key=self._signer.api_creds.api_key,
                    api_secret=self._signer.api_creds.api_secret,
                    api_passphrase=self._signer.api_creds.api_passphrase,
                )
            )
        else:
            client = ClobClient(host=self._host, chain_id=self._chain_id)
        return client

    async def _run(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous SDK method in the default thread pool.

        Connects lazily if ``connect()`` has not been called yet.

        Raises
        ------
        MarketNotFoundError
            When the SDK returns HTTP 404.
        RateLimitError
            When the SDK returns HTTP 429.
        PolymarketConnectionError
            For network-level failures.
        PolymarketError
            For all other SDK errors.
        """
        if self._client is None:
            await self.connect()

        func = getattr(self._client, method)
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except PolyApiException as e:
            if e.status_code == 404:
                raise MarketNotFoundError(str(e.error_msg)) from e
            if e.status_code == 429:
                raise RateLimitError(str(e.error_msg)) from e
            raise PolymarketError(str(e)) from e
        except PolyException as e:
            raise PolymarketError(str(e)) from e
        except Exception as e:
            err_name = type(e).__name__
            if "Connect" in err_name or "Timeout" in err_name or "Connection" in err_name:
                raise PolymarketConnectionError(str(e)) from e
            raise PolymarketError(str(e)) from e

    def _parse_market(self, data: dict[str, Any]) -> MarketSummary:
        """Transform a raw market dict into a :class:`MarketSummary`."""
        condition_id = data.get("condition_id", "")
        closed = data.get("closed", False)
        tick_size = float(data.get("minimum_tick_size", 0.01))
        min_size = float(data.get("minimum_order_size", 1.0))
        neg_risk = data.get("neg_risk", False)
        created_at = _parse_timestamp(data.get("accepting_order_timestamp"))

        tokens = data.get("tokens", [])
        if tokens:
            token = tokens[0]
            return MarketSummary(
                market_id=condition_id,
                condition_id=condition_id,
                token_id=token.get("token_id", ""),
                outcome=token.get("outcome", ""),
                price=float(token.get("price", 0)),
                tick_size=tick_size,
                min_size=min_size,
                neg_risk=neg_risk,
                closed=closed,
                created_at=created_at or datetime.now(),
            )

        return MarketSummary(
            market_id=condition_id,
            condition_id=condition_id,
            token_id=data.get("token_id", ""),
            outcome=data.get("outcome", ""),
            price=float(data.get("price", 0)),
            tick_size=tick_size,
            min_size=min_size,
            neg_risk=neg_risk,
            closed=closed,
            created_at=created_at or datetime.now(),
        )

    @staticmethod
    def _parse_order(data: dict[str, Any]) -> OrderResult:
        """Transform a raw order dict into an :class:`OrderResult`."""
        created_at = _parse_timestamp(
            data.get("created_at") or data.get("timestamp") or data.get("date")
        )
        return OrderResult(
            order_id=data.get("id", "") or data.get("order_id", ""),
            status=data.get("status", "unknown"),
            market_id=data.get("market", "") or data.get("market_id", ""),
            side=data.get("side", "UNKNOWN"),
            price=str(data.get("price", "0")),
            size=str(data.get("size", "0")),
            filled_size=str(data.get("filled_size", "0") or data.get("taker_amount", "0")),
            remaining_size=str(data.get("remaining_size", "0")),
            created_at=created_at or datetime.now(),
            error=data.get("error"),
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _parse_timestamp(ts: Any) -> datetime | None:
    """Parse a timestamp in various formats to :class:`datetime`."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, int | float):
        return datetime.utcfromtimestamp(ts)
    if isinstance(ts, str):
        ts_clean = ts.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(ts_clean)
        except (ValueError, TypeError):
            pass
    return None
