"""
Tests for Composite factor strategy.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot
from polymind.factors.registry import FactorMetadata, FactorSignalModel
from polymind.strategies.factors.composite.strategy import CompositeConfig, CompositeFactor


class ConstSignal(FactorSignalModel):
    def __init__(self, name: str, score: float):
        super().__init__(FactorMetadata(name=name))
        self._score = score

    async def compute_scores(self, universe: UniverseSnapshot) -> dict[str, float]:
        return dict.fromkeys(universe.markets, self._score)


class TestCompositeFactor:
    @pytest.mark.asyncio
    async def test_blends_signals(self):
        u = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={"m1": MarketFeatures(market_id="m1", mid_price=0.5)},
        )
        cf = CompositeFactor(
            sub_factors={"a": ConstSignal("a", 1.0), "b": ConstSignal("b", 0.0)},
            config=CompositeConfig(weights={"a": 0.5, "b": 0.5}, normalize=False),
        )
        scores = await cf.compute_scores(u)
        assert scores["m1"] == 0.5  # (1.0 * 0.5) + (0.0 * 0.5)

    @pytest.mark.asyncio
    async def test_zero_weight_skipped(self):
        cf = CompositeFactor(
            sub_factors={"a": ConstSignal("a", 1.0)},
            config=CompositeConfig(weights={"a": 0.0}),
        )
        u = UniverseSnapshot(timestamp=datetime.now(), markets={"m1": None})
        scores = await cf.compute_scores(u)
        assert scores == {}
