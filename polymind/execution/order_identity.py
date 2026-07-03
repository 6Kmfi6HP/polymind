"""
Stable, deterministic order identity for the entire order lifecycle.

An OrderIdentity uniquely identifies an order intent from creation through
fill, cancel, and replace.  It is derived from the intent payload so the
same intent produces the same identity across restarts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from polymind.core.intents import OrderSide


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
    client_id: str  # unique within (strategy_name, market_id) scope

    def to_identity_string(self) -> str:
        """Return a canonical string for logging and SDK exchange_order_id."""
        return (
            f"{self.strategy_name}:{self.market_id}:"
            f"{self.side.value}:{self.price}:"
            f"{self.outcome or '_'}:{self.client_id}"
        )
