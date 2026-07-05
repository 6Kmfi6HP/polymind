"""Tests for factor features computation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.factors.features import (
    FeatureComputer,
    compute_depth_imbalance,
    compute_micro_price,
    compute_spread_bps,
    compute_weighted_mid,
    momentum_from_history,
    volatility_from_history,
)


class TestComputeSpreadBps:
    def test_normal_spread(self) -> None:
        bid, ask = 0.45, 0.55
        result = compute_spread_bps(bid, ask)
        # (0.55 - 0.45) / 0.50 * 10000 = 2000
        assert result == pytest.approx(2000.0, rel=1e-3)

    def test_tight_spread(self) -> None:
        bid, ask = 0.498, 0.502
        result = compute_spread_bps(bid, ask)
        # (0.502 - 0.498) / 0.50 * 10000 = 80
        assert result == pytest.approx(80.0, rel=1e-3)

    def test_zero_mid_returns_inf(self) -> None:
        result = compute_spread_bps(0.0, 0.0)
        assert result == float("inf")

    def test_negative_bid_raises(self) -> None:
        with pytest.raises(ValueError, match="must be non-negative"):
            compute_spread_bps(-0.1, 0.5)

    def test_bid_greater_than_ask_raises(self) -> None:
        with pytest.raises(ValueError, match="must be less than or equal"):
            compute_spread_bps(0.6, 0.4)


class TestComputeMicroPrice:
    def test_micro_price_equals_mid_when_symmetric(self) -> None:
        result = compute_micro_price(0.45, 0.55, 1000.0, 1000.0)
        # Equal sizes → micro_price = mid = 0.50
        assert result == pytest.approx(0.50, rel=1e-3)

    def test_micro_price_biased_by_liquidity(self) -> None:
        result = compute_micro_price(0.45, 0.55, 5000.0, 1000.0)
        # More bid liquidity → micro_price weighted toward ask side
        assert result > 0.50  # Pushed above mid
        assert 0.45 < result < 0.55
        assert result == pytest.approx(0.5333, rel=1e-3)

    def test_micro_price_ask_heavy(self) -> None:
        result = compute_micro_price(0.45, 0.55, 500.0, 5000.0)
        # More ask liquidity → micro_price weighted toward bid side
        assert result < 0.50  # Pushed below mid
        assert 0.45 < result < 0.55

    def test_zero_sizes_returns_mid(self) -> None:
        result = compute_micro_price(0.45, 0.55, 0.0, 0.0)
        assert result == pytest.approx(0.50, rel=1e-3)

    def test_zero_bid_or_ask_price(self) -> None:
        result = compute_micro_price(0.0, 0.55, 1000.0, 1000.0)
        assert result < 0.55


class TestComputeWeightedMid:
    def test_symmetric_returns_mid(self) -> None:
        result = compute_weighted_mid(0.45, 0.55, 1000.0, 1000.0)
        assert result == pytest.approx(0.50, rel=1e-3)

    def test_bid_heavy_biased_to_bid(self) -> None:
        result = compute_weighted_mid(0.45, 0.55, 5000.0, 1000.0)
        # More bid size → weighted mid closer to bid
        assert result < 0.50
        assert result > 0.45
        assert result == pytest.approx(0.4667, rel=1e-3)

    def test_zero_total_size_returns_mid(self) -> None:
        result = compute_weighted_mid(0.45, 0.55, 0.0, 0.0)
        assert result == pytest.approx(0.50, rel=1e-3)


class TestComputeDepthImbalance:
    def test_symmetric_returns_zero(self) -> None:
        result = compute_depth_imbalance(1000.0, 1000.0)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_bid_heavy_positive(self) -> None:
        result = compute_depth_imbalance(5000.0, 1000.0)
        assert result > 0.0
        assert result <= 1.0

    def test_ask_heavy_negative(self) -> None:
        result = compute_depth_imbalance(500.0, 5000.0)
        assert result < 0.0
        assert result >= -1.0

    def test_zero_sizes(self) -> None:
        result = compute_depth_imbalance(0.0, 0.0)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_only_bid_size(self) -> None:
        result = compute_depth_imbalance(1000.0, 0.0)
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_only_ask_size(self) -> None:
        result = compute_depth_imbalance(0.0, 1000.0)
        assert result == pytest.approx(-1.0, abs=1e-6)


class TestMomentumFromHistory:
    def test_upward_momentum_positive(self) -> None:
        prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        result = momentum_from_history(prices, lookback=5)
        assert result is not None
        assert result > 0.0

    def test_downward_momentum_negative(self) -> None:
        prices = [15.0, 14.0, 13.0, 12.0, 11.0, 10.0]
        result = momentum_from_history(prices, lookback=5)
        assert result is not None
        assert result < 0.0

    def test_flat_returns_zero(self) -> None:
        prices = [10.0] * 10
        result = momentum_from_history(prices, lookback=5)
        assert result is not None
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_not_enough_history_returns_none(self) -> None:
        prices = [10.0, 11.0]
        result = momentum_from_history(prices, lookback=5)
        assert result is None

    def test_single_price_returns_none(self) -> None:
        result = momentum_from_history([10.0], lookback=1)
        assert result is None

    def test_lookback_zero_returns_none(self) -> None:
        result = momentum_from_history([10.0, 11.0, 12.0], lookback=0)
        assert result is None

    def test_lookback_longer_than_history(self) -> None:
        prices = [10.0, 11.0, 12.0]
        result = momentum_from_history(prices, lookback=10)
        assert result is None

    def test_edge_prices_not_zero(self) -> None:
        prices = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        result = momentum_from_history(prices, lookback=5)
        assert result is not None
        assert result > 0.0

    def test_zero_past_price_returns_none(self) -> None:
        """Line 173: past price is 0 → return None."""
        result = momentum_from_history([5.0, 0.0, 5.0], lookback=1)
        # `past = prices[-(1+1)] = prices[-2] = 0.0` → returns None
        assert result is None

    def test_lookback_of_one_requires_two_prices(self) -> None:
        """Exactly lookback+1 prices should work."""
        result = momentum_from_history([10.0, 12.0], lookback=1)
        assert result is not None
        assert result == pytest.approx(0.20, rel=1e-3)


class TestVolatilityFromHistory:
    def test_constant_prices_zero_volatility(self) -> None:
        prices = [10.0] * 10
        result = volatility_from_history(prices)
        assert result is not None
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_volatile_prices_positive(self) -> None:
        prices = [10.0, 20.0, 10.0, 20.0, 10.0, 20.0]
        result = volatility_from_history(prices)
        assert result is not None
        assert result > 0.0

    def test_not_enough_data_returns_none(self) -> None:
        result = volatility_from_history([10.0])
        assert result is None

    def test_empty_list_returns_none(self) -> None:
        result = volatility_from_history([])
        assert result is None

    def test_window_too_small_returns_none(self) -> None:
        """Lookback that results in < 2 prices returns None."""
        result = volatility_from_history([10.0, 12.0], lookback=1)
        # window = prices[-1:] = [12.0], len < 2 → None
        assert result is None

    def test_all_negative_prices_returns_none(self) -> None:
        """When all log returns are invalid, volatility returns None."""
        prices = [-1.0, -2.0, -3.0, -4.0, -5.0]
        result = volatility_from_history(prices)
        # All prices are non-positive → no valid log returns → None
        assert result is None


class TestFeatureComputer:
    @pytest.fixture
    def computer(self) -> FeatureComputer:
        return FeatureComputer(window=5)

    def test_compute_returns_basic_features(self, computer: FeatureComputer) -> None:
        ts = datetime.now(timezone.utc)
        mf = computer.compute(
            market_id="0xm1",
            bid_price=0.45,
            ask_price=0.55,
            bid_size=1000.0,
            ask_size=2000.0,
            volume_24h=50000.0,
            timestamp=ts,
        )
        assert mf.market_id == "0xm1"
        assert mf.mid_price == pytest.approx(0.50, rel=1e-3)
        assert mf.spread_bps == pytest.approx(2000.0, rel=1e-3)
        assert mf.volume_24h == pytest.approx(50000.0)
        assert mf.additional["micro_price"] > 0
        assert mf.additional["weighted_mid"] > 0
        assert "depth_imbalance" in mf.additional

    def test_momentum_after_multiple_observations(self, computer: FeatureComputer) -> None:
        ts = datetime.now(timezone.utc)
        # Inject increasing mid prices for momentum
        for i in range(6):
            bid = 0.40 + i * 0.02
            ask = 0.50 + i * 0.02
            computer.compute("0xm1", bid, ask, 1000.0, 1000.0, 50000.0, timestamp=ts)

        mf = computer.compute("0xm1", 0.52, 0.58, 1000.0, 1000.0, 50000.0, timestamp=ts)
        assert mf.momentum_4h is not None
        assert mf.momentum_24h is not None

    def test_separate_markets_have_separate_history(self, computer: FeatureComputer) -> None:
        ts = datetime.now(timezone.utc)
        for _ in range(6):
            computer.compute("0xm1", 0.45, 0.55, 1000.0, 1000.0, 50000.0, timestamp=ts)
            computer.compute("0xm2", 0.65, 0.75, 1000.0, 1000.0, 50000.0, timestamp=ts)

        mf1 = computer.compute("0xm1", 0.45, 0.55, 1000.0, 1000.0, 50000.0, timestamp=ts)
        mf2 = computer.compute("0xm2", 0.65, 0.75, 1000.0, 1000.0, 50000.0, timestamp=ts)
        assert mf1.momentum_4h is not None or mf2.momentum_4h is not None

    def test_market_returns_none_momentum_without_history(self, computer: FeatureComputer) -> None:
        ts = datetime.now(timezone.utc)
        mf = computer.compute("0xm1", 0.45, 0.55, 1000.0, 1000.0, 50000.0, timestamp=ts)
        assert mf.momentum_4h is None

    def test_compute_universe(self, computer: FeatureComputer) -> None:
        ts = datetime.now(timezone.utc)
        raw_data = {
            "0xm1": {
                "bid": 0.45,
                "ask": 0.55,
                "bid_size": 1000.0,
                "ask_size": 2000.0,
                "volume": 50000.0,
            },
            "0xm2": {
                "bid": 0.65,
                "ask": 0.75,
                "bid_size": 500.0,
                "ask_size": 500.0,
                "volume": 10000.0,
            },
        }
        universe = computer.compute_universe(raw_data, timestamp=ts)
        assert len(universe.markets) == 2
        assert universe.timestamp == ts
        assert "0xm1" in universe.markets
        assert "0xm2" in universe.markets
        assert universe.markets["0xm1"].mid_price == pytest.approx(0.50, rel=1e-3)
        assert universe.markets["0xm2"].mid_price == pytest.approx(0.70, rel=1e-3)

    def test_volatility_accumulates(self, computer: FeatureComputer) -> None:
        ts = datetime.now(timezone.utc)
        # Push volatile mid prices
        prices = [0.50, 0.55, 0.48, 0.58, 0.45, 0.60, 0.52]
        for p in prices:
            computer.compute("0xm1", p - 0.05, p + 0.05, 1000.0, 1000.0, 50000.0, timestamp=ts)

        mf = computer.compute("0xm1", 0.47, 0.57, 1000.0, 1000.0, 50000.0, timestamp=ts)
        assert mf.volatility_24h is not None
        assert mf.volatility_24h > 0.0

    def test_history_property(self, computer: FeatureComputer) -> None:
        """History property returns a copy of internal state."""
        ts = datetime.now(timezone.utc)
        computer.compute("0xm1", 0.45, 0.55, 1000.0, 1000.0, 50000.0, timestamp=ts)
        h = computer.history
        assert "0xm1" in h
        assert len(h["0xm1"]) == 1
        assert h["0xm1"][0] == pytest.approx(0.50, rel=1e-3)
        # Mutating returned dict should not affect internal state
        h["0xm2"] = [0.99]
        assert "0xm2" not in computer.history

    def test_clear_history_all(self, computer: FeatureComputer) -> None:
        ts = datetime.now(timezone.utc)
        computer.compute("0xm1", 0.45, 0.55, 1000.0, 1000.0, 50000.0, timestamp=ts)
        computer.compute("0xm2", 0.65, 0.75, 1000.0, 1000.0, 50000.0, timestamp=ts)
        assert len(computer.history) == 2
        computer.clear_history()
        assert len(computer.history) == 0

    def test_clear_history_one_market(self, computer: FeatureComputer) -> None:
        ts = datetime.now(timezone.utc)
        computer.compute("0xm1", 0.45, 0.55, 1000.0, 1000.0, 50000.0, timestamp=ts)
        computer.compute("0xm2", 0.65, 0.75, 1000.0, 1000.0, 50000.0, timestamp=ts)
        assert len(computer.history) == 2
        computer.clear_history("0xm1")
        assert "0xm1" not in computer.history
        assert "0xm2" in computer.history

    def test_clear_history_unknown_market(self, computer: FeatureComputer) -> None:
        """Clearing history for an unknown market does nothing."""
        computer.clear_history("nonexistent")
        assert len(computer.history) == 0
