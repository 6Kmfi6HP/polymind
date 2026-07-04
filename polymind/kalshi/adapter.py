"""
Kalshi exchange adapter — REST API client for prediction market trading.

Implements the ExchangeAdapter ABC from polymind.core.exchange.
"""

from __future__ import annotations

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


class KalshiConfig:
    """Configuration for the Kalshi adapter.

    Parameters
    ----------
    email:
        Kalshi account email.
    password:
        Kalshi account password.
    base_url:
        API base URL (default: production).
    """

    def __init__(
        self,
        email: str = "",
        password: str = "",
        base_url: str = "https://trading-api.kalshi.com/trade-api/v2",
    ) -> None:
        self.email = email
        self.password = password
        self.base_url = base_url


class KalshiAdapter(ExchangeAdapter):
    """Kalshi exchange adapter.

    Provides market data queries and order management for the
    Kalshi prediction market platform.

    Usage::

        adapter = KalshiAdapter(KalshiConfig(email="...", password="..."))
        await adapter.connect()
        markets = await adapter.get_markets()
        ob = await adapter.get_order_book("market-id")
        result = await adapter.place_order("market-id", "yes", 0.50, 100)
        await adapter.close()
    """

    def __init__(self, config: KalshiConfig | None = None) -> None:
        self._config = config or KalshiConfig()
        self._client: httpx.AsyncClient | None = None
        self._token: str | None = None
        self._name: str = "kalshi"

    @property
    def name(self) -> str:
        return self._name

    @property
    def connected(self) -> bool:
        return self._client is not None

    # ── Connection lifecycle ──────────────────────────────────────────

    async def connect(self) -> None:
        """Establish connection and authenticate."""
        self._client = httpx.AsyncClient(base_url=self._config.base_url)
        if self._config.email and self._config.password:
            await self._login()

    async def _login(self) -> None:
        """Authenticate and store session token."""
        if not self._client:
            return
        resp = await self._client.post(
            "/login",
            json={"email": self._config.email, "password": self._config.password},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("token")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _require_client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._client

    # ── Market data ───────────────────────────────────────────────────

    async def get_markets(self, active: bool = True, limit: int = 50) -> list[MarketInfo]:
        """Fetch available markets."""
        client = self._require_client()
        params: dict[str, Any] = {"limit": limit}
        if active:
            params["status"] = "open"

        resp = await client.get("/markets", params=params)
        resp.raise_for_status()
        data = resp.json()

        markets: list[MarketInfo] = []
        for m in data.get("markets", []):
            markets.append(
                MarketInfo(
                    market_id=m.get("id", ""),
                    title=m.get("title", ""),
                    outcomes=["YES", "NO"],
                    status=m.get("status", "active"),
                )
            )
        return markets

    async def get_order_book(self, market_id: str) -> OrderBook | None:
        """Fetch order book for a market."""
        client = self._require_client()
        resp = await client.get(f"/markets/{market_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        market = data.get("market", {})

        bids_raw = market.get("yes_bids", []) or market.get("bids", [])
        asks_raw = market.get("yes_asks", []) or market.get("asks", [])

        bids = [
            OrderBookLevel(price=float(b.get("price", 0)), size=float(b.get("count", 0)))
            for b in bids_raw
        ]
        asks = [
            OrderBookLevel(price=float(a.get("price", 0)), size=float(a.get("count", 0)))
            for a in asks_raw
        ]

        return OrderBook(
            market_id=market_id,
            bids=bids,
            asks=asks,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_market(self, market_id: str) -> MarketInfo | None:
        """Fetch a single market by ID."""
        client = self._require_client()
        resp = await client.get(f"/markets/{market_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json().get("market", {})
        return MarketInfo(
            market_id=data.get("id", market_id),
            title=data.get("title", ""),
            outcomes=["YES", "NO"],
            status=data.get("status", "active"),
        )

    # ── Trading ───────────────────────────────────────────────────────

    async def place_order(
        self,
        market_id: str,
        side: str,
        price: float,
        size: float,
        **kwargs: Any,
    ) -> OrderResult:
        """Place a limit order."""
        client = self._require_client()
        outcome = kwargs.get("outcome", side)
        payload = {
            "market_id": market_id,
            "side": "yes" if outcome.upper() == "YES" else "no",
            "price": int(price * 100),  # Kalshi uses cents
            "count": int(size),
        }
        resp = await client.post("/orders", json=payload)
        data = resp.json()
        order = data.get("order", {})

        return OrderResult(
            order_id=order.get("id", ""),
            status=order.get("status", "failed"),
            market_id=market_id,
            side=payload["side"],
            price=price,
            size=size,
            filled_size=float(order.get("filled_count", 0)),
            error=data.get("error") if resp.status_code >= 400 else None,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        client = self._require_client()
        resp = await client.delete(f"/orders/{order_id}")
        return resp.status_code == 200

    async def cancel_all_orders(self, market_id: str | None = None) -> int:
        """Cancel all open orders, optionally filtered by market."""
        client = self._require_client()
        params = {}
        if market_id:
            params["market_id"] = market_id
        resp = await client.delete("/orders", params=params)
        if resp.status_code == 200:
            data = resp.json()
            return int(data.get("cancelled_count", 0))
        return 0

    async def get_positions(self) -> list[Position]:
        """Fetch current positions."""
        client = self._require_client()
        resp = await client.get("/portfolio/positions")
        resp.raise_for_status()
        positions: list[Position] = []
        for p in resp.json().get("positions", []):
            positions.append(
                Position(
                    market_id=p.get("market_id", ""),
                    side="YES" if p.get("side") == "yes" else "NO",
                    size=float(p.get("count", 0)),
                    entry_price=float(p.get("price", 0)),
                )
            )
        return positions

    async def get_balance(self) -> float:
        """Fetch account balance (USDC)."""
        client = self._require_client()
        resp = await client.get("/portfolio/balance")
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("balance", 0))
