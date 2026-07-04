"""
Factor registry and base contracts.

Manages registration and discovery of factor signal models, tradability
filters, and portfolio constructors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from polymind.core.intents import StrategyIntent
from polymind.core.plugin import PluginRegistry
from polymind.core.portfolio import PortfolioTarget
from polymind.factors.pipeline import UniverseSnapshot


@dataclass
class FactorMetadata:
    """Metadata for a registered factor."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    lookback: str = "24h"  # default lookback
    tags: list[str] = field(default_factory=list)


class FactorSignalModel(ABC):
    """Computes signal scores from validated snapshots and feature panels."""

    def __init__(self, metadata: FactorMetadata):
        self.metadata = metadata

    @abstractmethod
    async def compute_scores(self, universe: UniverseSnapshot) -> dict[str, float]:
        """Score all markets in the universe. Returns market_id → score."""
        ...


class FactorExecutionBridge(ABC):
    """Converts a portfolio target into order intents for the executor."""

    @abstractmethod
    async def to_order_intents(self, target: PortfolioTarget) -> list[StrategyIntent]:
        """Convert a single PortfolioTarget into executable intents."""
        ...


class FactorRegistry:
    """Registry for factor signal models.

    Factors register by name. The registry enables discovery, validation,
    and lifecycle management.
    """

    def __init__(self):
        self._signals: dict[str, FactorSignalModel] = {}
        self._bridges: dict[str, FactorExecutionBridge] = {}

    def register_signal(self, name: str, model: FactorSignalModel) -> None:
        """Register a factor signal model under *name*.

        Also registers the model's class with the global PluginRegistry so
        that discovered plugins appear alongside built-in signals.
        """
        self._signals[name] = model
        PluginRegistry().register_factor(name, model.__class__)

    def register_bridge(self, name: str, bridge: FactorExecutionBridge) -> None:
        """Register an execution bridge for a factor."""
        self._bridges[name] = bridge

    def get_signal(self, name: str) -> FactorSignalModel | None:
        """Get a registered signal model by name.

        Falls back to the global PluginRegistry so that any
        externally-discovered factor can be lazily instantiated.
        """
        if name in self._signals:
            return self._signals[name]
        cls = PluginRegistry().get_factor(name)
        if cls is not None:
            return cls(FactorMetadata(name=name))
        return None

    def get_bridge(self, name: str) -> FactorExecutionBridge | None:
        """Get a registered execution bridge by name."""
        return self._bridges.get(name)

    def list_signals(self) -> list[str]:
        """List all registered signal names, merging with PluginRegistry."""
        builtin = list(self._signals.keys())
        discovered = list(PluginRegistry().list_factors().keys())
        return list(dict.fromkeys(builtin + discovered))  # deduped, order-preserving

    def list_bridges(self) -> list[str]:
        """List all registered bridge names."""
        return list(self._bridges.keys())

    def remove_signal(self, name: str) -> None:
        """Remove a registered signal from local dict and PluginRegistry."""
        self._signals.pop(name, None)
        PluginRegistry().remove_factor(name)

    def remove_bridge(self, name: str) -> None:
        """Remove a registered bridge."""
        self._bridges.pop(name, None)


def register_builtin_factors() -> None:
    """Register all built-in factor signal model classes in PluginRegistry.

    Registered classes can be discovered via :meth:`PluginRegistry.list_factors`
    and lazily resolved through :meth:`FactorRegistry.get_signal`.
    """
    from polymind.strategies.factors.fair_value.strategy import FairValueFactor
    from polymind.strategies.factors.momentum.strategy import MomentumFactor
    from polymind.strategies.factors.sentiment.strategy import SentimentFactor
    from polymind.strategies.factors.volatility.strategy import VolatilityFactor

    factors: list[tuple[str, type]] = [
        ("momentum", MomentumFactor),
        ("volatility", VolatilityFactor),
        ("sentiment", SentimentFactor),
        ("fair_value", FairValueFactor),
    ]
    for name, cls in factors:
        PluginRegistry().register_factor(name, cls)
