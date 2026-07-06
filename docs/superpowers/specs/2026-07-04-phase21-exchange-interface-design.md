> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 21: Multi-Exchange Adapter Interface — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

Architecture Phase 9 explicitly lists multi-platform support as an extension.
This phase defines the abstract interface that any venue adapter must implement,
enabling Polymind to eventually trade on Kalshi, Limitless, and other platforms.

## Abstract Interface

A new `polymind/core/exchange.py` module defines `ExchangeAdapter`:

```python
class ExchangeAdapter(ABC):
    """Interface all venue adapters must implement."""

    async def connect(self) -> None: ...
    async def close(self) -> None: ...

    # Market data
    async def get_markets(self, active: bool = True, limit: int = 50) -> list[MarketInfo]: ...
    async def get_order_book(self, market_id: str) -> OrderBook: ...

    # Trading
    async def place_order(self, market_id: str, side: str, price: float, size: float, **kwargs) -> OrderResult: ...
    async def cancel_order(self, order_id: str) -> bool: ...
    async def cancel_all_orders(self, market_id: str | None = None) -> int: ...

    # Account
    async def get_positions(self) -> list[Position]: ...
    async def get_balance(self) -> float: ...

    # Status
    @property
    def name(self) -> str: ...
    @property
    def connected(self) -> bool: ...
```

Shared domain types for the interface live in `polymind/core/types.py`.

The existing `PolymarketClient` will be refactored to implement this interface
in a future phase (non-breaking — all current code continues to work).
