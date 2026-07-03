"""
Base strategy class for all market-making strategies.

Every strategy in Polymind follows this interface. Strategies are
pluggable modules that define how to analyze, price, and execute
market-making on a given Polymarket.

Per ADR 0002, strategies produce ``StrategyIntent`` objects; executors
own CLOB transport, retries, and order lifecycle.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from polymind.core.intents import StrategyIntent


@dataclass
class StrategyConfig:
    """Configuration for a market-making strategy."""
    name: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategySignal:
    """Signal produced by a strategy's analysis phase.

    .. deprecated::
       Use :class:`StrategyIntent` instead.  This class is kept for
       backward compatibility during the migration to ADR 0002.
    """
    action: str  # "place", "cancel", "hold", "close"
    market_id: str
    outcome: str | None = None
    side: str | None = None
    price: float | None = None
    size: float = 0.0
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseMMStrategy(ABC):
    """
    Abstract base for all market-making strategies.

    A strategy defines:
    - Which markets to trade (filter/select)
    - How to price orders (bid/ask calculation)
    - How to size orders (position management)
    - How to manage risk (stop-loss, drawdown)
    """

    def __init__(self, config: StrategyConfig | None = None):
        self.config = config or StrategyConfig(name=self.__class__.__name__)
        self.name = self.config.name

    # ── Primary analysis interface (ADR 0002) ──────────────────────────────

    @abstractmethod
    async def analyze(self, market: Any) -> StrategyIntent | None:
        """
        Analyze a market and produce a StrategyIntent.

        Called per-market during the observe phase.  Returns ``None``
        when no action is required.

        This replaces the older ``analyze()`` that returned
        ``StrategySignal``.  Subclasses should migrate to returning
        ``StrategyIntent``.
        """
        ...

    # ── Legacy signal interface ────────────────────────────────────────────

    async def analyze_to_signal(self, market: Any) -> StrategySignal | None:
        """
        Legacy analysis method returning ``StrategySignal``.

        Default implementation delegates to :meth:`analyze` and converts
        the first order intent to a signal.  Override this directly if
        your strategy has not yet migrated to ``StrategyIntent``.
        """
        intent = await self.analyze(market)
        if intent is None or intent.is_empty():
            return None

        order = intent.orders[0] if intent.orders else None
        if order is None:
            return StrategySignal(
                action="hold",
                market_id=(
                    intent.cancels[0].market_id if intent.cancels else ""
                ),
            )

        return StrategySignal(
            action="place",
            market_id=order.market_id,
            outcome=order.outcome,
            side=order.side.value,
            price=order.price,
            size=order.size,
            confidence=1.0,
            metadata=order.metadata,
        )

    # ── Legacy order placement (deprecated) ─────────────────────────────────

    async def place_orders(self, signal: StrategySignal) -> list[Any]:
        """
        Place orders based on a trading signal.

        .. deprecated::
           Execution is now owned by :class:`IntentExecutor`.
           This method exists for backward compatibility.
        """
        ...

    async def manage_positions(self) -> None:
        """Manage existing positions (take profit, stop loss, merge)."""
        ...

    async def risk_check(self) -> bool:
        """
        Check if strategy should continue operating.
        Return False to trigger emergency stop.
        """
        return True

    def get_config_summary(self) -> dict[str, Any]:
        """Return human-readable config summary."""
        return {
            "strategy": self.name,
            "params": self.config.params,
        }
