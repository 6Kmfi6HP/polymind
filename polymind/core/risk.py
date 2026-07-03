"""
Risk decision contracts (Phase 2).

Risk gates sit between strategy decisions and execution. Each gate inspects
a StrategyIntent and returns a RiskDecision.  Gates are composable and
independent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from polymind.core.intents import StrategyIntent


@dataclass
class RiskDecision:
    """Decision from a single risk gate."""

    gate_name: str
    approved: bool
    reason: str
    overrides: dict[str, float] | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskContext:
    """Context provided to every risk gate."""

    current_positions: dict[str, float]
    current_exposure: float
    daily_pnl: float
    is_kill_switch_active: bool
    portfolio_value: float


class RiskGate(ABC):
    """A single composable risk check."""

    name: str

    @abstractmethod
    async def evaluate(
        self,
        intent: StrategyIntent,
        context: RiskContext,
    ) -> RiskDecision: ...
