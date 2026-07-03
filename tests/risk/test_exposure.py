"""
Tests for exposure management.
"""

from __future__ import annotations

from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.risk.exposure import ExposureConfig, ExposureManager


class TestExposureManager:
    def test_valid_target_passes(self):
        mgr = ExposureManager(ExposureConfig(max_exposure_per_market=100.0))
        t = PortfolioTarget("0xabc", PositionDirection.LONG, 50.0, 0.8, 1)
        approved = mgr.validate_targets([t])
        assert len(approved) == 1

    def test_excessive_exposure_rejected(self):
        mgr = ExposureManager(ExposureConfig(max_exposure_per_market=100.0))
        t = PortfolioTarget("0xabc", PositionDirection.LONG, 200.0, 0.8, 1)
        approved = mgr.validate_targets([t])
        assert len(approved) == 0

    def test_total_exposure_limit(self):
        mgr = ExposureManager(
            ExposureConfig(max_exposure_per_market=100.0, max_exposure_total=150.0)
        )
        t1 = PortfolioTarget("0xabc", PositionDirection.LONG, 100.0, 0.8, 1)
        t2 = PortfolioTarget("0xdef", PositionDirection.LONG, 100.0, 0.8, 2)
        approved = mgr.validate_targets([t1, t2])
        assert len(approved) == 1  # total would exceed

    def test_update_and_get_exposure(self):
        mgr = ExposureManager()
        t = PortfolioTarget("0xabc", PositionDirection.LONG, 50.0, 0.8, 1)
        mgr.update_positions([t])
        assert mgr.get_exposure("0xabc") == 50.0

    def test_unknown_market_exposure(self):
        mgr = ExposureManager()
        assert mgr.get_exposure("nonexistent") == 0.0
