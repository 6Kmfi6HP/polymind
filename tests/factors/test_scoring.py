"""
Tests for factor scoring functions.
"""

from __future__ import annotations

from datetime import datetime

from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot
from polymind.factors.scoring import momentum_score, rank_normalize


def _make_universe(features: list[dict]) -> UniverseSnapshot:
    markets = {}
    for f in features:
        mid = f.pop("market_id")
        markets[mid] = MarketFeatures(market_id=mid, **f)
    return UniverseSnapshot(timestamp=datetime.now(), markets=markets)


class TestMomentumScore:
    def test_momentum_4h(self):
        u = _make_universe(
            [
                {"market_id": "m1", "momentum_4h": 0.02},
                {"market_id": "m2", "momentum_4h": -0.01},
            ]
        )
        scores = momentum_score(u, lookback="4h")
        assert scores["m1"] == 0.02
        assert scores["m2"] == -0.01

    def test_momentum_7d(self):
        u = _make_universe(
            [
                {"market_id": "m1", "momentum_7d": 0.15},
            ]
        )
        scores = momentum_score(u, lookback="7d")
        assert scores["m1"] == 0.15

    def test_missing_momentum_skipped(self):
        u = _make_universe(
            [
                {"market_id": "m1", "momentum_24h": None},
            ]
        )
        scores = momentum_score(u, lookback="24h")
        assert scores == {}

    def test_empty_universe(self):
        u = UniverseSnapshot(timestamp=datetime.now(), markets={})
        scores = momentum_score(u)
        assert scores == {}


class TestRankNormalize:
    def test_normalize_two(self):
        scores = {"m1": 0.1, "m2": 0.9}
        ranked = rank_normalize(scores)
        assert ranked["m2"] == 1.0
        assert ranked["m1"] == 0.0

    def test_normalize_three(self):
        scores = {"m1": 0.1, "m2": 0.5, "m3": 0.9}
        ranked = rank_normalize(scores)
        assert ranked["m1"] == 0.0
        assert ranked["m2"] == 0.5
        assert ranked["m3"] == 1.0

    def test_empty(self):
        assert rank_normalize({}) == {}
