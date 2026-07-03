"""
Factor registry and base contracts.

Manages registration and discovery of factor signal models, tradability
filters, and portfolio constructors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from polymind.core.portfolio import PortfolioTarget
from polymind.core.intents import StrategyIntent
from polymind.factors.pipeline import UniverseSnapshot


@dataclass
class FactorMetadata:
    """Metadata for a registered factor."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    lookback: str = "24h"  # default lookback
    tags: List[str] = field(default_factory=list)


class FactorSignalModel(ABC):
    """Computes signal scores from validated snapshots and feature panels."""

    def __init__(self, metadata: FactorMetadata):
        self.metadata = metadata

    @abstractmethod
    async def compute_scores(self, universe: UniverseSnapshot) -> Dict[str, float]:
        """Score all markets in the universe. Returns market_id → score."""
        ...


class FactorExecutionBridge(ABC):
    """Converts a portfolio target into order intents for the executor."""

    @abstractmethod
    async def to_order_intents(
        self, target: PortfolioTarget
    ) -> List[StrategyIntent]:
        """Convert a single PortfolioTarget into executable intents."""
        ...


class FactorRegistry:
    """Registry for factor signal models.

    Factors register by name. The registry enables discovery, validation,
    and lifecycle management.
    """

    def __init__(self):
        self._signals: Dict[str, FactorSignalModel] = {}
        self._bridges: Dict[str, FactorExecutionBridge] = {}

    def register_signal(
        self, name: str, model: FactorSignalModel
    ) -> None:
        """Register a factor signal model."""
        self._signals[name] = model

    def register_bridge(
        self, name: str, bridge: FactorExecutionBridge
    ) -> None:
        """Register an execution bridge for a factor."""
        self._bridges[name] = bridge

    def get_signal(self, name: str) -> Optional[FactorSignalModel]:
        """Get a registered signal model by name."""
        return self._signals.get(name)

    def get_bridge(self, name: str) -> Optional[FactorExecutionBridge]:
        """Get a registered execution bridge by name."""
        return self._bridges.get(name)

    def list_signals(self) -> List[str]:
        """List all registered signal names."""
        return list(self._signals.keys())

    def list_bridges(self) -> List[str]:
        """List all registered bridge names."""
        return list(self._bridges.keys())

    def remove_signal(self, name: str) -> None:
        """Remove a registered signal."""
        self._signals.pop(name, None)

    def remove_bridge(self, name: str) -> None:
        """Remove a registered bridge."""
        self._bridges.pop(name, None)
