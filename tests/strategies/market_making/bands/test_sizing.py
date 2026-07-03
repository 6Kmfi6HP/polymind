"""
Tests for Bands sizing.
"""

from __future__ import annotations

import pytest

from polymind.strategies.market_making.bands.pricing import BandConfig, BandPricingConfig
from polymind.strategies.market_making.bands.sizing import BandSizingConfig, distribute_band_sizes


class TestBandSizingConfig:
    def test_default(self):
        cfg = BandSizingConfig()
        assert cfg.exposure_per_band == 20.0

    def test_custom(self):
        cfg = BandSizingConfig(exposure_per_band=50.0)
        assert cfg.exposure_per_band == 50.0


class TestDistributeBandSizes:
    def test_default_bands(self):
        """Default 3 bands with weight=1.0 should get equal sizes."""
        cfg = BandPricingConfig()
        sizes = distribute_band_sizes(cfg, BandSizingConfig())
        assert len(sizes) == 3
        assert sizes == pytest.approx([20.0, 20.0, 20.0])

    def test_weighted_bands(self):
        """Bands with different weights should get proportional sizes."""
        bands = [
            BandConfig(spread_pct=0.01, weight=2.0),
            BandConfig(spread_pct=0.03, weight=1.0),
            BandConfig(spread_pct=0.06, weight=0.5),
        ]
        cfg = BandPricingConfig(bands=bands)
        sizes = distribute_band_sizes(cfg, BandSizingConfig(exposure_per_band=10.0))
        assert sizes == pytest.approx([20.0, 10.0, 5.0])

    def test_single_band(self):
        """Single band with weight 1.0."""
        bands = [BandConfig(spread_pct=0.02)]
        cfg = BandPricingConfig(bands=bands)
        sizes = distribute_band_sizes(cfg, BandSizingConfig(exposure_per_band=15.0))
        assert sizes == [15.0]

    def test_custom_exposure(self):
        """Custom exposure_per_band should scale all sizes."""
        bands = [
            BandConfig(spread_pct=0.01, weight=1.0),
            BandConfig(spread_pct=0.03, weight=1.0),
        ]
        cfg = BandPricingConfig(bands=bands)
        sizes = distribute_band_sizes(cfg, BandSizingConfig(exposure_per_band=100.0))
        assert sizes == [100.0, 100.0]
