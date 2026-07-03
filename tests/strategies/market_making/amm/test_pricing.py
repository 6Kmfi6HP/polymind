"""
Tests for AMM ladder pricing.
"""

from __future__ import annotations

import pytest

from polymind.strategies.market_making.amm.pricing import AMMPricingConfig, compute_ladder


class TestAMMPricingConfig:
    def test_defaults(self):
        cfg = AMMPricingConfig()
        assert cfg.min_spread == 0.01
        assert cfg.max_spread == 0.05
        assert cfg.num_levels == 5
        assert cfg.tick_size == 0.001

    def test_custom(self):
        cfg = AMMPricingConfig(min_spread=0.02, max_spread=0.10, num_levels=10, tick_size=0.005)
        assert cfg.num_levels == 10
        assert cfg.tick_size == 0.005


class TestComputeLadder:
    def test_symmetry(self):
        """Ladder should be symmetric around target price."""
        cfg = AMMPricingConfig(num_levels=3)
        ladder = compute_ladder(target_price=1.0, config=cfg)
        buys = [p for s, p, sz in ladder if s.value == "BUY"]
        sells = [p for s, p, sz in ladder if s.value == "SELL"]
        # Same number of buys and sells
        assert len(buys) == len(sells) == 3
        # Sells above target, buys below target
        assert all(p >= 1.0 for p in sells)
        assert all(p <= 1.0 for p in buys)

    def test_num_levels(self):
        """Should produce exactly num_levels buy + num_levels sell orders."""
        cfg = AMMPricingConfig(num_levels=5)
        ladder = compute_ladder(target_price=0.5, config=cfg)
        assert len(ladder) == 10  # 5 buys + 5 sells

    def test_spread_range(self):
        """Inner levels should be within min_spread, outer within max_spread."""
        cfg = AMMPricingConfig(min_spread=0.01, max_spread=0.05, num_levels=5)
        ladder = compute_ladder(target_price=1.0, config=cfg)
        for _side, price, _ in ladder:
            spread = abs(price - 1.0) / 1.0
            assert spread >= 0.005, f"Spread {spread} too tight"
            assert spread <= 0.06, f"Spread {spread} too wide"

    def test_all_prices_positive(self):
        """All prices should be positive."""
        cfg = AMMPricingConfig()
        ladder = compute_ladder(target_price=0.1, config=cfg)
        for _, price, _ in ladder:
            assert price > 0

    def test_target_price_zero_returns_empty(self):
        """Zero target price should produce no orders."""
        cfg = AMMPricingConfig()
        ladder = compute_ladder(target_price=0.0, config=cfg)
        assert ladder == []

    def test_single_level(self):
        """With 1 level, should produce 1 buy and 1 sell."""
        cfg = AMMPricingConfig(num_levels=1, min_spread=0.01, max_spread=0.01)
        ladder = compute_ladder(target_price=1.0, config=cfg)
        assert len(ladder) == 2
        assert ladder[0][0].value == "BUY"
        assert ladder[1][0].value == "SELL"

    def test_prices_rounded_to_tick(self):
        """Prices should be rounded to nearest tick_size."""
        cfg = AMMPricingConfig(tick_size=0.01, min_spread=0.01, max_spread=0.03, num_levels=2)
        ladder = compute_ladder(target_price=1.0, config=cfg)
        for _, price, _ in ladder:
            # Price should be multiple of tick_size (to 2 decimal places)
            assert round(price, 6) == pytest.approx(round(price, 6), abs=1e-10)
            remainder = price % 0.01
            assert remainder < 1e-10 or abs(remainder - 0.01) < 1e-10
