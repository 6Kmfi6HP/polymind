"""
Tests for portfolio construction.
"""

from __future__ import annotations

from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.factors.portfolio_construction import (
    PortfolioConfig,
    construct_portfolio,
    select_top_and_bottom_n,
    select_top_n,
    size_by_rank,
)


class TestSelectTopN:
    def test_top_2_of_5(self):
        scores = {"a": 0.9, "b": 0.7, "c": 0.5, "d": 0.3, "e": 0.1}
        selected = select_top_n(scores, 2)
        assert selected == ["a", "b"]

    def test_top_more_than_available(self):
        scores = {"a": 0.9, "b": 0.7}
        selected = select_top_n(scores, 5)
        assert selected == ["a", "b"]

    def test_empty(self):
        assert select_top_n({}, 5) == []


class TestSelectTopAndBottomN:
    def test_long_short(self):
        scores = {"a": 0.9, "b": 0.7, "c": 0.5, "d": 0.3, "e": 0.1}
        directions = select_top_and_bottom_n(scores, 2)
        assert directions["a"] == PositionDirection.LONG
        assert directions["b"] == PositionDirection.LONG
        assert directions["d"] == PositionDirection.SHORT
        assert directions["e"] == PositionDirection.SHORT


class TestSizeByRank:
    def test_proportional_sizing(self):
        scores = {"a": 0.9, "b": 0.7, "c": 0.5}
        cfg = PortfolioConfig(max_exposure_per_market=100.0, total_exposure=500.0)
        sizes = size_by_rank(scores, cfg)
        # Higher score → larger size
        assert sizes["a"] > sizes["b"] > sizes["c"]

    def test_total_exposure_clamped(self):
        scores = {"a": 0.9, "b": 0.8}
        cfg = PortfolioConfig(max_exposure_per_market=100.0, total_exposure=50.0)
        sizes = size_by_rank(scores, cfg)
        assert sum(sizes.values()) <= cfg.total_exposure * 1.01  # allow rounding

    def test_empty(self):
        assert size_by_rank({}, PortfolioConfig()) == {}


class TestConstructPortfolio:
    def test_basic_construction(self):
        scores = {"a": 0.9, "b": 0.6, "c": 0.3, "d": -0.5, "e": -0.8}
        cfg = PortfolioConfig(top_n=3, max_exposure_per_market=100.0, total_exposure=300.0)
        targets = construct_portfolio(scores, cfg)
        assert len(targets) <= 3
        assert all(isinstance(t, PortfolioTarget) for t in targets)

    def test_direction_by_sign(self):
        scores = {"positive": 0.8, "negative": -0.7}
        cfg = PortfolioConfig(top_n=2)
        targets = construct_portfolio(scores, cfg)
        dirs = {t.market_id: t.direction for t in targets}
        assert dirs["positive"] == PositionDirection.LONG
        assert dirs["negative"] == PositionDirection.SHORT

    def test_min_confidence_filter(self):
        scores = {"a": 0.05, "b": 0.9}
        cfg = PortfolioConfig(top_n=2, min_confidence=0.1)
        targets = construct_portfolio(scores, cfg)
        mids = [t.market_id for t in targets]
        assert "b" in mids
        assert "a" not in mids

    def test_empty_scores(self):
        assert construct_portfolio({}, PortfolioConfig()) == []

    def test_rank_field(self):
        scores = {"a": 0.9, "b": 0.7}
        targets = construct_portfolio(scores, PortfolioConfig(top_n=2))
        ranks = {t.market_id: t.rank for t in targets}
        assert ranks["a"] < ranks["b"]  # higher score → lower rank number
