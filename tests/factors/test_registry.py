"""
Tests for factor registry and base contracts.
"""

from __future__ import annotations

from typing import Dict

import pytest

from polymind.core.portfolio import PortfolioTarget
from polymind.factors.pipeline import UniverseSnapshot
from polymind.factors.registry import (
    FactorExecutionBridge,
    FactorMetadata,
    FactorRegistry,
    FactorSignalModel,
)


class ConstantSignal(FactorSignalModel):
    """Test signal that returns constant scores."""

    async def compute_scores(self, universe: UniverseSnapshot) -> Dict[str, float]:
        return {mid: 0.5 for mid in universe.markets}


class DummyBridge(FactorExecutionBridge):
    """Test bridge that returns empty intents."""

    async def to_order_intents(self, target: PortfolioTarget) -> list:
        return []


class TestFactorMetadata:
    def test_minimal(self):
        m = FactorMetadata(name="mom_7d")
        assert m.name == "mom_7d"
        assert m.version == "0.1.0"

    def test_full(self):
        m = FactorMetadata(
            name="volatility",
            version="1.0.0",
            description="Volatility regime detector",
            lookback="7d",
            tags=["regime", "risk"],
        )
        assert m.lookback == "7d"
        assert "regime" in m.tags


class TestFactorSignalModel:
    @pytest.mark.asyncio
    async def test_constant_signal(self):
        from datetime import datetime

        model = ConstantSignal(FactorMetadata(name="test"))
        universe = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={"m1": None, "m2": None},  # type: ignore
        )
        scores = await model.compute_scores(universe)
        assert scores["m1"] == 0.5
        assert scores["m2"] == 0.5


class TestFactorRegistry:
    def test_register_and_get_signal(self):
        registry = FactorRegistry()
        model = ConstantSignal(FactorMetadata(name="test"))
        registry.register_signal("momentum_24h", model)
        assert registry.get_signal("momentum_24h") is model

    def test_register_and_get_bridge(self):
        registry = FactorRegistry()
        bridge = DummyBridge()
        registry.register_bridge("momentum_bridge", bridge)
        assert registry.get_bridge("momentum_bridge") is bridge

    def test_list_signals(self):
        registry = FactorRegistry()
        registry.register_signal(
            "a", ConstantSignal(FactorMetadata(name="a"))
        )
        registry.register_signal(
            "b", ConstantSignal(FactorMetadata(name="b"))
        )
        signals = registry.list_signals()
        assert "a" in signals
        assert "b" in signals

    def test_get_missing_returns_none(self):
        registry = FactorRegistry()
        assert registry.get_signal("nonexistent") is None
        assert registry.get_bridge("nonexistent") is None

    def test_remove_signal(self):
        registry = FactorRegistry()
        registry.register_signal(
            "x", ConstantSignal(FactorMetadata(name="x"))
        )
        registry.remove_signal("x")
        assert registry.get_signal("x") is None
