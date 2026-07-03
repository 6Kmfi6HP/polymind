"""
Ledger entry contracts (Phase 2).

Append-only entries in the paper or live P&L ledger, recording fills,
fees, merges, splits, redemptions, and cash adjustments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class EntryType(Enum):
    """Category of a ledger entry."""

    FILL = auto()
    FEE = auto()
    MERGE = auto()
    SPLIT = auto()
    REDEEM = auto()
    CASH_ADJUSTMENT = auto()
    CORRECTION = auto()


@dataclass
class LedgerEntry:
    """Immutable record of a value-changing event.

    The ledger is append-only. Once written, an entry is never mutated;
    corrections produce new entries with a reference to the superseded one.
    """

    entry_id: str
    entry_type: EntryType
    timestamp: datetime
    market_id: str
    description: str
    delta_cash: float
    delta_position: float
    position_after: float
    cash_after: float
    fill_ref: str | None = None
    supersedes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
