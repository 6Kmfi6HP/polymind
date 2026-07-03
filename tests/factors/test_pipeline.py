"""
Tests for FactorPipeline.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.factors.pipeline import (
    FactorPipeline,
    MarketFeatures,
    ScoreResult,
    UniverseSnapshot,
)


def identity_features(u: UniverseSnapshot) -> UniverseSnapshot:
    return u


def identity_filter(u: UniverseSnapshot) -> UniverseSnapshot:
    return u


def constant_score(u: UniverseSnapshot) -> ScoreResult:
    scores = {mid: 0.5 for mid in u.markets}
    return ScoreResult(scores=scores, timestamp=u.timestamp)


def single_target(scores: ScoreResult) -> list[PortfolioTarget]:
    if not scores.scores:
        return []
    mid = next(iter(scores.scores))
    return [
        PortfolioTarget(
            market_id=mid,
            direction=PositionDirection.LONG,
            target_size=10.0,
            confidence=0.5,
            rank=1,
        )
    ]


class TestUniverseSnapshot:
    def test_empty(self):
        u = UniverseSnapshot(timestamp=datetime.now())
        assert u.markets == {}

    def test_with_markets(self):
        u = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={
                "0xabc": MarketFeatures(market_id="0xabc", mid_price=0.5),
            },
        )
        assert len(u.markets) == 1


class TestMarketFeatures:
    def test_minimal(self):
        f = MarketFeatures(market_id="0xabc")
        assert f.market_id == "0xabc"

    def test_full(self):
        f = MarketFeatures(
            market_id="0xabc",
            mid_price=0.5,
            spread_bps=50.0,
            volume_24h=10000.0,
            momentum_4h=0.02,
            momentum_24h=0.05,
            momentum_7d=0.15,
            volatility_24h=0.1,
        )
        assert f.momentum_7d == 0.15
        assert f.volatility_24h == 0.1


class TestScoreResult:
    def test_construction(self):
        sr = ScoreResult(
            scores={"0xabc": 0.5, "0xdef": 0.3},
            timestamp=datetime.now(),
        )
        assert len(sr.scores) == 2
        assert sr.scores["0xabc"] == 0.5


class TestFactorPipeline:
    @pytest.mark.asyncio
    async def test_empty_universe(self):
        pipeline = FactorPipeline(
            feature_fn=identity_features,
            filter_fn=identity_filter,
            score_fn=lambda u: ScoreResult(scores={}, timestamp=u.timestamp),
            portfolio_fn=lambda s: [],
        )
        universe = UniverseSnapshot(timestamp=datetime.now())
        targets = await pipeline.run(universe)
        assert targets == []

    @pytest.mark.asyncio
    async def test_single_market(self):
        pipeline = FactorPipeline(
            feature_fn=identity_features,
            filter_fn=identity_filter,
            score_fn=constant_score,
            portfolio_fn=single_target,
        )
        universe = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={"0xabc": MarketFeatures(market_id="0xabc", mid_price=0.5)},
        )
        targets = await pipeline.run(universe)
        assert len(targets) == 1
        assert targets[0].market_id == "0xabc"
        assert targets[0].direction == PositionDirection.LONG

    @pytest.mark.asyncio
    async def test_filter_removes_markets(self):
        """Filter that removes a market should prevent it from being scored."""

        def strict_filter(u: UniverseSnapshot) -> UniverseSnapshot:
            # Only keep '0xabc'
            u.markets = {k: v for k, v in u.markets.items() if k == "0xabc"}
            return u

        def scoring(u: UniverseSnapshot) -> ScoreResult:
            scores = {mid: 0.5 for mid in u.markets}
            return ScoreResult(scores=scores, timestamp=u.timestamp)

        pipeline = FactorPipeline(
            feature_fn=identity_features,
            filter_fn=strict_filter,
            score_fn=scoring,
            portfolio_fn=lambda s: [
                PortfolioTarget(
                    market_id=mid,
                    direction=PositionDirection.LONG,
                    target_size=10.0,
                    confidence=0.5,
                    rank=i,
                )
                for i, mid in enumerate(s.scores)
            ],
        )
        universe = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={
                "0xabc": MarketFeatures(market_id="0xabc"),
                "0xdef": MarketFeatures(market_id="0xdef"),
            },
        )
        targets = await pipeline.run(universe)
        assert len(targets) == 1
        assert targets[0].market_id == "0xabc"
