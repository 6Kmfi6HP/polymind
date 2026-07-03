"""
Tests for tradability filters.
"""

from __future__ import annotations

from datetime import datetime

from polymind.factors.filters import (
    FilterConfig,
    apply_all_filters,
    filter_by_price,
    filter_by_spread,
    filter_by_volatility,
    filter_by_volume,
)
from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot


def _make_universe(markets: list[tuple[str, float, float, float, float]]) -> UniverseSnapshot:
    """Helper: create universe from list of (market_id, mid, spread_bps, vol_24h, vol_24h_pct)."""
    features = {}
    for mid, mid_price, spread_bps, vol_24h, vol_24h_pct in markets:
        features[mid] = MarketFeatures(
            market_id=mid,
            mid_price=mid_price,
            spread_bps=spread_bps,
            volume_24h=vol_24h,
            volatility_24h=vol_24h_pct,
        )
    return UniverseSnapshot(timestamp=datetime.now(), markets=features)


class TestFilterBySpread:
    def test_filters_wide_spread(self):
        u = _make_universe([("m1", 0.5, 50.0, 10000, 0.1), ("m2", 0.5, 200.0, 10000, 0.1)])
        cfg = FilterConfig(max_spread_bps=100.0)
        result = filter_by_spread(u, cfg)
        assert "m1" in result.markets
        assert "m2" not in result.markets

    def test_all_pass(self):
        u = _make_universe([("m1", 0.5, 50.0, 10000, 0.1), ("m2", 0.5, 30.0, 10000, 0.1)])
        cfg = FilterConfig(max_spread_bps=100.0)
        result = filter_by_spread(u, cfg)
        assert len(result.markets) == 2


class TestFilterByVolume:
    def test_filters_low_volume(self):
        u = _make_universe([("m1", 0.5, 50.0, 50000, 0.1), ("m2", 0.5, 50.0, 500, 0.1)])
        cfg = FilterConfig(min_volume_24h=1000.0)
        result = filter_by_volume(u, cfg)
        assert "m1" in result.markets
        assert "m2" not in result.markets


class TestFilterByVolatility:
    def test_filters_high_volatility(self):
        u = _make_universe([("m1", 0.5, 50.0, 10000, 0.3), ("m2", 0.5, 50.0, 10000, 0.8)])
        cfg = FilterConfig(max_volatility_24h=0.5)
        result = filter_by_volatility(u, cfg)
        assert "m1" in result.markets
        assert "m2" not in result.markets

    def test_none_volatility_passes(self):
        u = UniverseSnapshot(
            timestamp=datetime.now(),
            markets={
                "m1": MarketFeatures(market_id="m1", mid_price=0.5),
            },
        )
        cfg = FilterConfig(max_volatility_24h=0.5)
        result = filter_by_volatility(u, cfg)
        assert "m1" in result.markets


class TestFilterByPrice:
    def test_filters_low_price(self):
        u = _make_universe([("m1", 0.05, 50.0, 10000, 0.1), ("m2", 0.50, 50.0, 10000, 0.1)])
        cfg = FilterConfig(min_mid_price=0.1)
        result = filter_by_price(u, cfg)
        assert "m2" in result.markets
        assert "m1" not in result.markets


class TestApplyAllFilters:
    def test_removes_all_bad_markets(self):
        u = _make_universe(
            [
                ("good", 0.5, 50.0, 50000, 0.1),
                ("wide_spread", 0.5, 200.0, 50000, 0.1),
                ("low_volume", 0.5, 50.0, 100, 0.1),
                ("high_vol", 0.5, 50.0, 50000, 0.8),
                ("low_price", 0.005, 50.0, 50000, 0.1),
            ]
        )
        cfg = FilterConfig()
        result = apply_all_filters(u, cfg)
        assert "good" in result.markets
        assert "wide_spread" not in result.markets
        assert "low_volume" not in result.markets
        assert "high_vol" not in result.markets
        assert "low_price" not in result.markets

    def test_empty_universe(self):
        u = UniverseSnapshot(timestamp=datetime.now(), markets={})
        result = apply_all_filters(u, FilterConfig())
        assert result.markets == {}
