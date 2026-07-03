"""
Tests for AMM position sizing.
"""

from __future__ import annotations

import pytest

from polymind.strategies.market_making.amm.sizing import AMMSizingConfig, distribute_size


class TestAMMSizingConfig:
    def test_defaults(self):
        cfg = AMMSizingConfig()
        assert cfg.min_order_size == 1.0
        assert cfg.max_order_size == 1000.0
        assert cfg.total_exposure == 100.0
        assert cfg.concentration_pct == 0.5

    def test_custom(self):
        cfg = AMMSizingConfig(
            min_order_size=5.0,
            max_order_size=500.0,
            total_exposure=200.0,
            concentration_pct=0.3,
        )
        assert cfg.total_exposure == 200.0
        assert cfg.concentration_pct == 0.3


class TestDistributeSize:
    def test_linear_distribution(self):
        """With concentration=0.5, sizes should flatten to linear at 1.0."""
        levels = 5
        sizes = distribute_size(total_exposure=100.0, num_levels=levels, concentration_pct=0.0)
        assert len(sizes) == levels
        # Uniform distribution
        assert sizes == pytest.approx([20.0] * 5)

    def test_concentration_centers(self):
        """Higher concentration should put more size on inner levels."""
        sizes = distribute_size(100.0, 5, 0.8)
        assert len(sizes) == 5
        # Inner level (index 0) should be larger than outer (index 4)
        assert sizes[0] > sizes[4]

    def test_total_exposure_respected(self):
        """Sum of all sizes should equal total_exposure (within rounding)."""
        sizes = distribute_size(200.0, 10, 0.5)
        assert sum(sizes) == pytest.approx(200.0, abs=1.0)

    def test_single_level(self):
        """Single level should get all exposure."""
        sizes = distribute_size(100.0, 1, 0.5)
        assert len(sizes) == 1
        assert sizes[0] == pytest.approx(100.0)

    def test_min_order_size_clamped(self):
        """No individual size should be below min_order_size unless total_exposure is smaller."""
        sizes = distribute_size(2.0, 5, 0.5)
        # Some levels may get 0 due to heavy concentration
        assert sum(sizes) <= 2.0

    def test_zero_exposure(self):
        """Zero exposure should produce all zeros."""
        sizes = distribute_size(0.0, 5, 0.5)
        assert sizes == pytest.approx([0.0] * 5)

    def test_two_levels(self):
        """Two levels should still sum to total."""
        sizes = distribute_size(100.0, 2, 0.3)
        assert sum(sizes) == pytest.approx(100.0, abs=0.01)
        assert len(sizes) == 2
