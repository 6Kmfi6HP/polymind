"""
Tests for Momentum factor strategy.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot
from polymind.factors.portfolio_construction import PortfolioConfig, construct_portfolio
from polymind.factors.scoring import rank_normalize
from polymind.strategies.factors.momentum.strategy import (
    MomentumConfig,
    MomentumFactor,
)


def _make_universe(features: list[dict]) -> UniverseSnapshot:
    markets = {}
    for f in features:
        mid = f.pop("market_id")
        markets[mid] = MarketFeatures(market_id=mid, **f)
    return UniverseSnapshot(timestamp=datetime.now(), markets=markets)


class TestMomentumConfig:
    def test_defaults(self):
        cfg = MomentumConfig()
        assert cfg.lookback == "24h"
        assert cfg.top_n == 5
        assert cfg.long_short is True


class TestMomentumFactor:
    @pytest.mark.asyncio
    async def test_compute_scores(self):
        u = _make_universe([
            {"market_id": "m1", "momentum_24h": 0.05},
            {"market_id": "m2", "momentum_24h": -0.03},
            {"market_id": "m3", "momentum_24h": 0.01},
        ])
        model = MomentumFactor()
        scores = await model.compute_scores(u)
        assert scores["m1"] == 0.05
        assert scores["m2"] == -0.03
        assert scores["m3"] == 0.01

    @pytest.mark.asyncio
    async def test_lookback_7d(self):
        u = _make_universe([
            {"market_id": "m1", "momentum_7d": 0.15},
        ])
        cfg = MomentumConfig(lookback="7d")
        model = MomentumFactor(cfg)
        scores = await model.compute_scores(u)
        assert scores["m1"] == 0.15

    @pytest.mark.asyncio
    async def test_empty_universe(self):
        u = UniverseSnapshot(timestamp=datetime.now(), markets={})
        model = MomentumFactor()
        scores = await model.compute_scores(u)
        assert scores == {}

    def test_metadata_name(self):
        cfg = MomentumConfig(lookback="4h")
        model = MomentumFactor(cfg)
        assert model.metadata.name == "momentum_4h"
        assert "momentum" in model.metadata.tags

    @pytest.mark.asyncio
    async def test_full_pipeline_integration(self):
        """End-to-end: scores → rank → portfolio targets."""
        u = _make_universe([
            {"market_id": "m1", "momentum_24h": 0.10},
            {"market_id": "m2", "momentum_24h": 0.05},
            {"market_id": "m3", "momentum_24h": -0.02},
            {"market_id": "m4", "momentum_24h": -0.08},
            {"market_id": "m5", "momentum_24h": 0.01},
        ])
        model = MomentumFactor(MomentumConfig(top_n=3))
        scores = await model.compute_scores(u)
        ranked = rank_normalize(scores)

        cfg = PortfolioConfig(top_n=3)
        targets = construct_portfolio(ranked, cfg)
        assert 1 <= len(targets) <= 3
