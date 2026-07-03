"""
Portfolio target contracts (Phase 2).

Factor strategies produce PortfolioTargets as the output of their
portfolio construction step.  An execution bridge converts these into
OrderIntents for the executor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class PositionDirection(Enum):
    """Direction of a portfolio position."""

    LONG = auto()
    SHORT = auto()
    NEUTRAL = auto()


@dataclass
class PortfolioTarget:
    """A desired portfolio position produced by a factor or overlay strategy."""

    market_id: str
    direction: PositionDirection
    target_size: float  # in token/shares (not USD)
    confidence: float  # 0.0–1.0, from signal score
    rank: int  # decile / percentile rank among universe
    holding_period_hours: Optional[float] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
