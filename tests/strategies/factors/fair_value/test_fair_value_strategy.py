"""
Tests for Fair-Value factor strategy.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot
from polymind.strategies.factors.fair_value.strategy import FairValueConfig, FairValueFactor


class TestFairValueFactor:
    @pytest.mark.asyncio
    async def test_undervalued_positive_score(self):
        u = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={
                "m1": MarketFeatures(
                    market_id="m1", mid_price=0.5,
                    additional={"micro_price": 0.55},  # micro > mid = undervalued
                ),
            },
        )
        model = FairValueFactor()
        scores = await model.compute_scores(u)
        assert scores["m1"] > 0

    @pytest.mark.asyncio
    async def test_overvalued_negative_score(self):
        u = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={
                "m1": MarketFeatures(
                    market_id="m1", mid_price=0.5,
                    additional={"micro_price": 0.45},  # micro < mid = overvalued
                ),
            },
        )
        model = FairValueFactor()
        scores = await model.compute_scores(u)
        assert scores["m1"] < 0

    @pytest.mark.asyncio
    async def test_no_micro_price_skipped(self):
        u = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={"m1": MarketFeatures(market_id="m1", mid_price=0.5)},
        )
        model = FairValueFactor()
        scores = await model.compute_scores(u)
        assert scores == {}
