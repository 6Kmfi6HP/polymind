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

    @pytest.mark.asyncio
    async def test_normalize_true_via_min_max(self):
        """normalize=True calls _normalize which min-maxes varying scores."""

        class VarSignal(FactorSignalModel):
            def __init__(self):
                super().__init__(FactorMetadata(name="var"))

            async def compute_scores(self, universe):  # noqa
                return {"m1": 0.2, "m2": 0.8}

        u = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={
                "m1": MarketFeatures(market_id="m1", mid_price=0.5),
                "m2": MarketFeatures(market_id="m2", mid_price=1.0),
            },
        )
        cf = CompositeFactor(
            sub_factors={"v": VarSignal()},
            config=CompositeConfig(weights={"v": 1.0}, normalize=True),
        )
        scores = await cf.compute_scores(u)
        # VarSignal returns {"m1": 0.2, "m2": 0.8}
        # _normalize: min=0.2, max=0.8, diff=0.6
        #   m1: (0.2-0.2)/0.6 = 0.0
        #   m2: (0.8-0.2)/0.6 = 1.0
        # Weighted by 1.0: m1=0.0, m2=1.0
        assert scores["m1"] == pytest.approx(0.0)
        assert scores["m2"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_normalize_equal_scores_returns_half(self):
        """_normalize returns 0.5 for all keys when all scores are equal (diff == 0)."""
        u = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={
                "m1": MarketFeatures(market_id="m1", mid_price=0.5),
                "m2": MarketFeatures(market_id="m2", mid_price=1.0),
            },
        )
        cf = CompositeFactor(
            sub_factors={"a": ConstSignal("a", 1.0)},
            config=CompositeConfig(weights={"a": 1.0}, normalize=True),
        )
        scores = await cf.compute_scores(u)
        # ConstSignal returns {"m1": 1.0, "m2": 1.0}
        # _normalize: min=1.0, max=1.0, diff=0 → {"m1": 0.5, "m2": 0.5}
        assert scores["m1"] == 0.5
        assert scores["m2"] == 0.5

    @pytest.mark.asyncio
    async def test_normalize_empty_scores(self):
        """_normalize handles empty scores dict."""

        class EmptySignal(FactorSignalModel):
            def __init__(self):
                super().__init__(FactorMetadata(name="empty"))

            async def compute_scores(self, universe):  # noqa
                return {}

        u = UniverseSnapshot(timestamp=datetime.now(), markets={})
        cf = CompositeFactor(
            sub_factors={"e": EmptySignal()},
            config=CompositeConfig(weights={"e": 1.0}, normalize=True),
        )
        scores = await cf.compute_scores(u)
        assert scores == {}
