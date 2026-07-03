"""
Tests for Sentiment factor strategy.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot
from polymind.strategies.factors.sentiment.strategy import SentimentConfig, SentimentFactor


def _make_universe(features: list[dict]) -> UniverseSnapshot:
    markets = {}
    for f in features:
        mid = f.pop("market_id")
        markets[mid] = MarketFeatures(market_id=mid, **f)
    return UniverseSnapshot(timestamp=datetime.now(), markets=markets)


class TestSentimentFactor:
    @pytest.mark.asyncio
    async def test_from_additional(self):
        u = _make_universe([
            {"market_id": "m1", "additional": {"sentiment": 0.8}},
            {"market_id": "m2", "additional": {"sentiment": -0.3}},
        ])
        model = SentimentFactor()
        scores = await model.compute_scores(u)
        assert scores["m1"] == 0.8
        assert scores["m2"] == -0.3

    @pytest.mark.asyncio
    async def test_no_sentiment_skipped(self):
        u = _make_universe([
            {"market_id": "m1", "mid_price": 0.5},
        ])
        model = SentimentFactor()
        scores = await model.compute_scores(u)
        assert scores == {}

    @pytest.mark.asyncio
    async def test_config_source(self):
        cfg = SentimentConfig(source="news")
        model = SentimentFactor(cfg)
        assert "news" in model.metadata.name
