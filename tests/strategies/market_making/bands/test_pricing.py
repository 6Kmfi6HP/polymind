"""
Tests for Bands pricing.
"""

from __future__ import annotations

from polymind.strategies.market_making.bands.pricing import (
    BandConfig,
    BandPricingConfig,
    compute_band_prices,
)


class TestBandConfig:
    def test_minimal(self):
        band = BandConfig(spread_pct=0.02)
        assert band.spread_pct == 0.02
        assert band.weight == 1.0

    def test_with_weight(self):
        band = BandConfig(spread_pct=0.05, weight=2.0)
        assert band.weight == 2.0


class TestBandPricingConfig:
    def test_default(self):
        cfg = BandPricingConfig()
        assert len(cfg.bands) == 3

    def test_custom_bands(self):
        bands = [
            BandConfig(spread_pct=0.01),
            BandConfig(spread_pct=0.03),
            BandConfig(spread_pct=0.06),
            BandConfig(spread_pct=0.10),
        ]
        cfg = BandPricingConfig(bands=bands)
        assert len(cfg.bands) == 4


class TestComputeBandPrices:
    def test_two_bands_symmetric(self):
        """Two bands should produce 4 orders (2 buy + 2 sell)."""
        bands = [BandConfig(spread_pct=0.02), BandConfig(spread_pct=0.05)]
        cfg = BandPricingConfig(bands=bands)
        prices = compute_band_prices(target_price=1.0, config=cfg)
        assert len(prices) == 4

    def test_buys_below_target(self):
        """Buy orders should be below target price."""
        cfg = BandPricingConfig()
        prices = compute_band_prices(target_price=0.5, config=cfg)
        for side, price, _ in prices:
            if side.value == "BUY":
                assert price <= 0.5

    def test_sells_above_target(self):
        """Sell orders should be above target price."""
        cfg = BandPricingConfig()
        prices = compute_band_prices(target_price=0.5, config=cfg)
        for side, price, _ in prices:
            if side.value == "SELL":
                assert price >= 0.5

    def test_zero_target_returns_empty(self):
        """Zero target should produce no prices."""
        cfg = BandPricingConfig()
        prices = compute_band_prices(target_price=0.0, config=cfg)
        assert prices == []

    def test_band_indices_incremental(self):
        """Band indices should be 0, 1, 2, ..."""
        cfg = BandPricingConfig()
        prices = compute_band_prices(target_price=1.0, config=cfg)
        indices = [idx for _, _, idx in prices]
        assert indices == [0, 0, 1, 1, 2, 2]

    def test_all_prices_positive(self):
        """All band prices should be positive."""
        cfg = BandPricingConfig()
        prices = compute_band_prices(target_price=0.01, config=cfg)
        for _, price, _ in prices:
            assert price > 0

    def test_single_band(self):
        """Single band should produce 1 buy + 1 sell."""
        bands = [BandConfig(spread_pct=0.03)]
        cfg = BandPricingConfig(bands=bands)
        prices = compute_band_prices(target_price=1.0, config=cfg)
        assert len(prices) == 2
