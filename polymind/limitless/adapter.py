"""
Limitless exchange adapter — REST API + optional SDK for order signing.

Implements the ExchangeAdapter ABC from polymind.core.exchange.
Uses httpx for read operations and the `limitless-sdk` package
(optional) for EIP-712 order signing.

Install:  pip install polymind[limitless]
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from polymind.core.exchange import (
    ExchangeAdapter,
    MarketInfo,
    OrderBook,
    OrderBookLevel,
    OrderResult,
    Position,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class LimitlessConfig:
    """Configuration for the Limitless adapter.

    Parameters
    ----------
    api_key:
        Limitless API key. Falls back to ``LIMITLESS_API_KEY`` env var.
    private_key:
        Ethereum private key (0x-prefixed) for EIP-712 order signing.
        Falls back to ``LIMITLESS_PRIVATE_KEY`` env var.  Required only
        for order placement.
    base_url:
        API base URL (default: production).
    """

    api_key: str = ""
    private_key: str = ""
    base_url: str = "https://api.limitless.exchange"

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get("LIMITLESS_API_KEY", "")
        if not self.private_key:
            self.private_key = os.environ.get("LIMITLESS_PRIVATE_KEY", "")


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class LimitlessAdapter(ExchangeAdapter):
    """Limitless exchange adapter.

    Provides market data queries, order management, and portfolio access
    for the Limitless prediction market platform (Base chain).

    .. code-block:: python

        adapter = LimitlessAdapter(LimitlessConfig(api_key="..."))
        await adapter.connect()
        markets = await adapter.get_markets()
        ob = await adapter.get_order_book("bitcoin-2024")
        await adapter.close()
    """

    def __init__(self, config: LimitlessConfig | None = None) -> None:
        self._config = config or LimitlessConfig()
        self._client: httpx.AsyncClient | None = None
        self._order_client: Any = None  # OrderClient from limitless_sdk (optional)
        self._market_fetcher: Any = None  # MarketFetcher cache
        self._profile: dict[str, Any] | None = None  # cached profile
        self._name: str = "limitless"

    # -- Properties ---------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def connected(self) -> bool:
        return self._client is not None

    # -- Connection lifecycle -----------------------------------------------

    async def connect(self) -> None:
        """Initialise the HTTP client and set up order signing if available."""
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            headers={"X-API-Key": self._config.api_key},
        )

        # Try to initialise the SDK OrderClient for EIP-712 signing
        if self._config.private_key:
            self._order_client = self._try_init_order_client()

    def _try_init_order_client(self) -> Any | None:
        """Attempt to create a limitless_sdk OrderClient.

        Returns ``None`` silently when the SDK is not installed.
        Also stores SDK type references to avoid repeated imports.
        """
        try:
            from eth_account import Account
            from limitless_sdk.api import HttpClient as SdkHttpClient
            from limitless_sdk.markets import MarketFetcher
            from limitless_sdk.orders import OrderClient

            sdk_http = SdkHttpClient(
                base_url=self._config.base_url,
                api_key=self._config.api_key,
            )
            self._market_fetcher = MarketFetcher(sdk_http)
            wallet = Account.from_key(self._config.private_key)
            return OrderClient(http_client=sdk_http, wallet=wallet)
        except ImportError:
            return None

    def _get_sdk_enums(self) -> tuple[Any, Any, Any]:
        """Return ``(Side, OrderType, OrderType)`` from limitless_sdk.

        Raises RuntimeError if the SDK is not available.
        """
        try:
            from limitless_sdk.types import OrderType as LimitlessOrderType
            from limitless_sdk.types import Side as LimitlessSide

            return LimitlessSide, LimitlessOrderType, LimitlessOrderType
        except ImportError as exc:
            raise RuntimeError(
                "Order placement requires `limitless-sdk` package. "
                "Install with: pip install limitless-sdk"
            ) from exc

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _require_client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._client

    # -- Market data --------------------------------------------------------

    async def get_markets(self, active: bool = True, limit: int = 50) -> list[MarketInfo]:
        """Fetch active markets from Limitless."""
        client = self._require_client()
        params: dict[str, Any] = {"limit": min(limit, 100)}
        if active:
            params["status"] = "active"

        resp = await client.get("/markets/active", params=params)
        resp.raise_for_status()
        data = resp.json()

        markets: list[MarketInfo] = []
        for m in data.get("data", []):
            markets.append(
                MarketInfo(
                    market_id=m.get("slug", ""),
                    title=m.get("title", m.get("slug", "")),
                    outcomes=self._extract_outcomes(m),
                    status=m.get("status", "active"),
                )
            )
        return markets

    async def get_market(self, slug: str) -> MarketInfo | None:
        """Fetch a single market by slug."""
        client = self._require_client()
        resp = await client.get(f"/markets/{slug}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

        return MarketInfo(
            market_id=data.get("slug", slug),
            title=data.get("title", slug),
            outcomes=self._extract_outcomes(data),
            status=data.get("status", "active"),
        )

    async def get_order_book(self, market_id: str) -> OrderBook | None:
        """Fetch the current orderbook for a market.

        ``market_id`` is the market slug on Limitless.
        """
        client = self._require_client()
        resp = await client.get(f"/markets/{market_id}/orderbook")
        if resp.status_code == 404:
            return None
        if resp.status_code == 400:
            # AMM markets don't support orderbook
            return None
        resp.raise_for_status()
        data = resp.json()

        bids = [
            OrderBookLevel(price=float(b.get("price", 0)), size=float(b.get("size", 0)))
            for b in data.get("bids", [])
        ]
        asks = [
            OrderBookLevel(price=float(a.get("price", 0)), size=float(a.get("size", 0)))
            for a in data.get("asks", [])
        ]

        return OrderBook(
            market_id=market_id,
            bids=bids,
            asks=asks,
            timestamp=datetime.now(timezone.utc),
        )

    # -- Trading ------------------------------------------------------------

    async def place_order(
        self,
        market_id: str,
        side: str,
        price: float,
        size: float,
        **kwargs: Any,
    ) -> OrderResult:
        """Place an order on Limitless.

        Requires the ``limitless-sdk`` package and a configured private key
        for EIP-712 signing.

        Parameters
        ----------
        market_id:
            Market slug (e.g. ``"bitcoin-2024"``).
        side:
            ``"BUY"`` or ``"SELL"``.
        price:
            Price in USDC (0.00 – 1.00).
        size:
            Number of shares.
        **kwargs:
            ``order_type`` (``"GTC"``, ``"FAK"``, ``"FOK"``; default ``"GTC"``),
            ``post_only`` (bool).

        Returns
        -------
        OrderResult
        """
        if not self._order_client:
            raise RuntimeError(
                "Order placement requires `limitless-sdk` package and a configured "
                "private key. Install with: pip install limitless-sdk"
            )

        import contextlib

        # Ensure venue data is cached
        if self._market_fetcher:
            with contextlib.suppress(Exception):
                await self._market_fetcher.get_market(market_id)

        Side, OrderType, _ = self._get_sdk_enums()

        side_enum = Side.BUY if side.upper() == "BUY" else Side.SELL
        order_type_str = kwargs.get("order_type", "GTC").upper()

        type_map = {
            "GTC": OrderType.GTC,
            "FAK": OrderType.FAK,
            "FOK": OrderType.FOK,
        }
        order_type = type_map.get(order_type_str, OrderType.GTC)
        post_only = kwargs.get("post_only", order_type == OrderType.GTC)

        # Resolve token_id from market data
        token_id = kwargs.get("token_id", "")
        if not token_id:
            token_id = await self._resolve_token_id(market_id, side)

        try:
            order = await self._order_client.create_order(
                token_id=token_id,
                price=price,
                size=size,
                side=side_enum,
                order_type=order_type,
                market_slug=market_id,
                post_only=post_only,
            )
        except Exception as exc:
            return OrderResult(
                order_id="",
                status="failed",
                market_id=market_id,
                side=side.upper(),
                price=price,
                size=size,
                error=str(exc),
            )

        return OrderResult(
            order_id=getattr(order, "order", {}).get("id", ""),
            status=getattr(order, "order", {}).get("status", "open"),
            market_id=market_id,
            side=side.upper(),
            price=price,
            size=size,
            filled_size=float(getattr(order, "order", {}).get("filled_size", 0)),
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a single open order by its UUID."""
        client = self._require_client()
        resp = await client.delete(f"/orders/{order_id}")
        return resp.status_code == 200

    async def cancel_all_orders(self, market_id: str | None = None) -> int:
        """Cancel all open orders, optionally filtered by market slug."""
        if market_id and self._order_client:
            # Use SDK for market-scoped cancel
            try:
                await self._order_client.cancel_all(market_id)
                return -1  # SDK doesn't return count
            except Exception:
                pass

        client = self._require_client()
        if market_id:
            resp = await client.delete(f"/orders/all/{market_id}")
        else:
            # Cancel all across all markets — POST batch-cancel
            resp = await client.post("/orders/batch-cancel", json={})

        if resp.status_code == 200:
            data = resp.json()
            cancelled = data.get("cancelled", [])
            return len(cancelled) if isinstance(cancelled, list) else 1
        return 0

    # -- Account ------------------------------------------------------------

    async def get_positions(self) -> list[Position]:
        """Fetch current open positions."""
        client = self._require_client()
        resp = await client.get("/portfolio/positions")
        resp.raise_for_status()
        positions: list[Position] = []
        for p in resp.json().get("clob", []):
            positions.append(
                Position(
                    market_id=p.get("slug", ""),
                    side="LONG" if float(p.get("shares", 0)) > 0 else "SHORT",
                    size=abs(float(p.get("shares", 0))),
                    entry_price=float(p.get("avgPrice", p.get("entryPrice", 0))),
                    unrealized_pnl=float(p.get("unrealizedPnl", 0)),
                )
            )
        return positions

    async def get_balance(self) -> float:
        """Fetch available balance (USDC)."""
        client = self._require_client()
        resp = await client.get("/profiles/me")
        resp.raise_for_status()
        data = resp.json()
        # Balance field varies; try common names
        return float(
            data.get("balance") or data.get("usdcBalance") or data.get("availableBalance") or 0
        )

    # -- Helpers ------------------------------------------------------------

    async def _resolve_token_id(self, slug: str, side: str) -> str:
        """Resolve the YES or NO token ID for a market slug.

        Uses the REST API as a fallback when the SDK client isn't available.
        """
        client = self._require_client()
        resp = await client.get(f"/markets/{slug}")
        if resp.status_code != 200:
            return ""
        data = resp.json()
        tokens = data.get("tokens", {})
        return str(tokens.get("yes", "")) if side.upper() == "BUY" else str(tokens.get("no", ""))

    @staticmethod
    def _extract_outcomes(market_data: dict[str, Any]) -> list[str]:
        """Extract outcome labels from market data."""
        outcomes = market_data.get("outcomes", [])
        if outcomes:
            return outcomes
        # Derive from token presence
        tokens = market_data.get("tokens", {})
        if tokens.get("yes") or tokens.get("no"):
            return ["YES", "NO"]
        return []
