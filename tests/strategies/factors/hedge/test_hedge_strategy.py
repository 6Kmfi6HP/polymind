"""
Tests for Hedge overlay.
"""

from __future__ import annotations

from datetime import datetime

from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.factors.pipeline import UniverseSnapshot
from polymind.strategies.factors.hedge.strategy import HedgeConfig, HedgeOverlay


def _empty_universe() -> UniverseSnapshot:
    return UniverseSnapshot(timestamp=datetime.now(), markets={})


class TestHedgeOverlay:
    def test_no_hedge_when_balanced(self):
        overlay = HedgeOverlay()
        targets = [
            PortfolioTarget("a", PositionDirection.LONG, 50.0, 0.8, 1),
            PortfolioTarget("b", PositionDirection.SHORT, 50.0, 0.8, 2),
        ]
        result = overlay.apply(targets, _empty_universe())
        # balanced → no hedge added
        assert len(result) == 2

    def test_adds_hedge_when_imbalanced_long(self):
        overlay = HedgeOverlay()
        targets = [
            PortfolioTarget("a", PositionDirection.LONG, 100.0, 0.8, 1),
            PortfolioTarget("b", PositionDirection.SHORT, 50.0, 0.8, 2),
        ]
        result = overlay.apply(targets, _empty_universe())
        assert len(result) == 3  # original 2 + hedge

    def test_net_exposure_long(self):
        overlay = HedgeOverlay()
        targets = [
            PortfolioTarget("a", PositionDirection.LONG, 100.0, 0.8, 1),
            PortfolioTarget("b", PositionDirection.SHORT, 30.0, 0.8, 2),
        ]
        net = overlay.compute_net_exposure(targets)
        assert net == 70.0  # 100 - 30

    def test_net_exposure_zero(self):
        overlay = HedgeOverlay()
        targets = [
            PortfolioTarget("a", PositionDirection.LONG, 50.0, 0.8, 1),
            PortfolioTarget("b", PositionDirection.SHORT, 50.0, 0.8, 2),
        ]
        net = overlay.compute_net_exposure(targets)
        assert net == 0.0

    def test_hedge_ratio_half(self):
        overlay = HedgeOverlay(HedgeConfig(hedge_ratio=0.5))
        targets = [
            PortfolioTarget("a", PositionDirection.LONG, 100.0, 0.8, 1),
        ]
        result = overlay.apply(targets, _empty_universe())
        assert len(result) == 2
        hedge = [t for t in result if t.market_id == "HEDGE"][0]
        assert hedge.target_size == 50.0  # 100 * 0.5
