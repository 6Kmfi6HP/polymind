"""
Tests for Volatility factor strategy.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot
from polymind.strategies.factors.volatility.strategy import VolatilityConfig, VolatilityFactor


def _make_universe(features: list[dict]) -> UniverseSnapshot:
    markets = {}
    for f in features:
        mid = f.pop("market_id")
        markets[mid] = MarketFeatures(market_id=mid, **f)
    return UniverseSnapshot(timestamp=datetime.now(), markets=markets)


class TestVolatilityFactor:
    @pytest.mark.asyncio
    async def test_high_vol_scores_higher(self):
        u = _make_universe(
            [
                {"market_id": "m1", "volatility_24h": 0.5},
                {"market_id": "m2", "volatility_24h": 0.1},
            ]
        )
        model = VolatilityFactor()
        scores = await model.compute_scores(u)
        assert scores["m1"] > scores["m2"]

    @pytest.mark.asyncio
    async def test_inverted(self):
        u = _make_universe(
            [
                {"market_id": "m1", "volatility_24h": 0.5},
                {"market_id": "m2", "volatility_24h": 0.1},
            ]
        )
        cfg = VolatilityConfig(invert=True)
        model = VolatilityFactor(cfg)
        scores = await model.compute_scores(u)
        assert scores["m1"] < scores["m2"]

    @pytest.mark.asyncio
    async def test_metadata_name(self):
        model = VolatilityFactor()
        assert "volatility" in model.metadata.name
        assert "volatility" in model.metadata.tags

    @pytest.mark.asyncio
    async def test_missing_vol_skipped(self):
        u = _make_universe(
            [
                {"market_id": "m1", "mid_price": 0.5},
            ]
        )
        model = VolatilityFactor()
        scores = await model.compute_scores(u)
        assert scores == {}
