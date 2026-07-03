"""
Per-market/per-token command serializer for safe order placement.

Serializes OrderIntent to the Polymarket API format.  Price and size
validation/rounding protect against dust orders and off-tick prices.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from polymind.core.intents import OrderIntent

# ── Domain types ─────────────────────────────────────────────────────────────


@dataclass
class SerializerConfig:
    """Tick and size constraints for a single market/token pair.

    Attributes:
        tick_size: Minimum price increment (e.g. 0.01 for 1-cent ticks).
        min_size: Minimum order size (e.g. 1.0).
        price_decimals: Decimal places for price string output.
        size_decimals: Decimal places for size string output.
    """

    tick_size: float = 0.01
    min_size: float = 1.0
    price_decimals: int = 2
    size_decimals: int = 2


@dataclass
class SerializedOrder:
    """Order payload ready for Polymarket CLOB API submission.

    Attributes:
        market_id: On-chain market identifier (hex string).
        token_id: On-chain token/outcome identifier (hex string).
        side: Order side string ("BUY" or "SELL").
        price: Formatted price string (e.g. "0.55").
        size: Formatted size string (e.g. "100.00").
        timestamp: When the serialization occurred.
    """

    market_id: str
    token_id: str
    side: str
    price: str
    size: str
    timestamp: datetime


# ── Serializer ───────────────────────────────────────────────────────────────


class OrderSerializer:
    """Serialize and validate OrderIntent values for a specific market/token.

    Each serializer is configured with the tick size and minimum size for a
    particular market+token pair, ensuring that every order placed through it
    conforms to exchange price/size constraints.
    """

    def __init__(self, config: SerializerConfig) -> None:
        self.config = config

    # ── Public API ─────────────────────────────────────────────────────────

    def serialize_intent(self, intent: OrderIntent, token_id: str) -> SerializedOrder:
        """Convert an ``OrderIntent`` into a ``SerializedOrder``.

        The price and size are rounded to the configured tick/min constraints
        before formatting to strings.
        """
        price = self.round_price(intent.price)
        size = self.round_size(intent.size)
        return SerializedOrder(
            market_id=intent.market_id,
            token_id=token_id,
            side=intent.side.value,
            price=f"{price:.{self.config.price_decimals}f}",
            size=f"{size:.{self.config.size_decimals}f}",
            timestamp=datetime.now(),
        )

    def serialize_cancel(self, market_id: str, order_id: str) -> dict[str, Any]:
        """Produce a cancel-order payload dict.

        Returns a minimal dict with ``market_id`` and ``order_id`` keys, as
        expected by the Polymarket API cancel endpoint.
        """
        return {
            "market_id": market_id,
            "order_id": order_id,
        }

    def validate_price(self, price: float) -> bool:
        """Return ``True`` when *price* is positive and aligns to ``tick_size``.

        A valid price is strictly greater than zero and an integer multiple of
        the configured tick size.
        """
        if price <= 0:
            return False
        return self._is_multiple(price, self.config.tick_size)

    def validate_size(self, size: float) -> bool:
        """Return ``True`` when *size* is positive and conforms to ``min_size``.

        A valid size is strictly greater than zero, at least ``min_size``, and
        an integer multiple of ``min_size``.
        """
        if size <= 0 or size < self.config.min_size:
            return False
        return self._is_multiple(size, self.config.min_size)

    def round_price(self, price: float) -> float:
        """Round *price* to the nearest ``tick_size`` increment, floor at ``tick_size``.

        Returns at least ``tick_size`` so that sub-tick values are not silently
        rounded to zero.
        """
        if price <= 0:
            return self.config.tick_size
        rounded = round(price / self.config.tick_size) * self.config.tick_size
        if rounded < self.config.tick_size:
            return self.config.tick_size
        return rounded

    def round_size(self, size: float) -> float:
        """Round *size* to the nearest ``min_size`` increment, floor at ``min_size``.

        Returns at least ``min_size`` so that rounding a very small value does
        not produce a sub-minimum order.
        """
        if size <= 0:
            return self.config.min_size
        rounded = round(size / self.config.min_size) * self.config.min_size
        if rounded < self.config.min_size:
            return self.config.min_size
        return rounded

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _is_multiple(value: float, granularity: float) -> bool:
        """Return ``True`` when *value* is an integer multiple of *granularity*."""
        if granularity <= 0:
            return False
        quotient = value / granularity
        return abs(quotient - round(quotient)) < 1e-9
