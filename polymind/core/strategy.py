"""
Base strategy class for all market-making strategies.

Every strategy in Polymind follows this interface. Strategies are
pluggable modules that define how to analyze, price, and execute
market-making on a given Polymarket.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StrategyConfig:
    """Configuration for a market-making strategy."""
    name: str
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategySignal:
    """Signal produced by a strategy's analysis phase."""
    action: str  # "place", "cancel", "hold", "close"
    market_id: str
    outcome: Optional[str] = None
    side: Optional[str] = None
    price: Optional[float] = None
    size: float = 0.0
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseMMStrategy(ABC):
    """
    Abstract base for all market-making strategies.

    A strategy defines:
    - Which markets to trade (filter/select)
    - How to price orders (bid/ask calculation)
    - How to size orders (position management)
    - How to manage risk (stop-loss, drawdown)
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        self.config = config or StrategyConfig(name=self.__class__.__name__)
        self.name = self.config.name

    @abstractmethod
    async def analyze(self, market: Any) -> Optional[StrategySignal]:
        """
        Analyze a market and produce a trading signal.

        Called per-market during the observe phase.
        Returns None if no action needed.
        """
        ...

    @abstractmethod
    async def place_orders(self, signal: StrategySignal) -> List[Any]:
        """
        Place orders based on a trading signal.

        Returns list of placed orders.
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

    def get_config_summary(self) -> Dict[str, Any]:
        """Return human-readable config summary."""
        return {
            "strategy": self.name,
            "params": self.config.params,
        }
