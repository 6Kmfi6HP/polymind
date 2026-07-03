"""
Fill event contracts (Phase 2).

A unified representation of a fill or partial fill, regardless of whether
it was detected via WebSocket event, CLOB API poll, or on-chain balance
reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from polymind.core.intents import OrderSide


class FillSource(Enum):
    """Origin of a fill detection."""

    WEBSOCKET = auto()
    CLOB_API = auto()
    ONCHAIN = auto()
    SIMULATED = auto()


@dataclass
class FillEvent:
    """A fill or partial fill detected by any channel."""

    fill_id: str
    market_id: str
    outcome: str  # "YES" or "NO"
    side: OrderSide
    price: float
    size: float
    fee: float
    timestamp: datetime
    source: FillSource
    order_id: str | None = None
    taker: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
