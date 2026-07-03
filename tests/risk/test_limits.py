"""Tests for risk limits module."""

from __future__ import annotations

from polymind.risk.limits import (
    DailyLossLimit,
    ExposureLimit,
    LimitsConfig,
    LimitsManager,
    OrderRateLimit,
    PositionLimit,
)


class TestPositionLimit:
    def test_construction(self):
        pl = PositionLimit(market_id="0xabc", max_size=100.0, max_notional=1000.0, min_size=1.0)
        assert pl.market_id == "0xabc"
        assert pl.max_size == 100.0
        assert pl.max_notional == 1000.0
        assert pl.min_size == 1.0

    def test_defaults(self):
        pl = PositionLimit(market_id="0xdef")
        assert pl.max_size == float("inf")
        assert pl.min_size == 0.0


class TestOrderRateLimit:
    def test_construction(self):
        rl = OrderRateLimit(max_orders_per_window=20, window_seconds=120)
        assert rl.max_orders_per_window == 20
        assert rl.window_seconds == 120


class TestDailyLossLimit:
    def test_construction(self):
        dl = DailyLossLimit(max_loss_amount=500.0, max_loss_pct=10.0)
        assert dl.max_loss_amount == 500.0
        assert dl.max_loss_pct == 10.0


class TestExposureLimit:
    def test_construction(self):
        el = ExposureLimit(max_total_exposure=10_000.0, max_per_market_pct=25.0)
        assert el.max_total_exposure == 10_000.0
        assert el.max_per_market_pct == 25.0


class TestLimitsConfig:
    def test_construction(self):
        pl = PositionLimit(market_id="0xabc", max_size=50.0)
        rl = OrderRateLimit(max_orders_per_window=5)
        dl = DailyLossLimit(max_loss_amount=200.0)
        el = ExposureLimit(max_total_exposure=5000.0)

        cfg = LimitsConfig(
            positions=[pl],
            order_rate=rl,
            daily_loss=dl,
            exposure=el,
        )
        assert len(cfg.positions) == 1
        assert cfg.positions[0] is pl
        assert cfg.order_rate is rl
        assert cfg.daily_loss is dl
        assert cfg.exposure is el

    def test_defaults(self):
        cfg = LimitsConfig()
        assert cfg.positions == []
        assert cfg.order_rate.max_orders_per_window == 10
        assert cfg.daily_loss.max_loss_amount == float("inf")
        assert cfg.exposure.max_total_exposure == float("inf")


class TestLimitsManager:
    def test_init_with_config(self):
        cfg = LimitsConfig()
        mgr = LimitsManager(config=cfg)
        assert mgr.config is cfg

    def test_check_position_size_within_limit(self):
        pl = PositionLimit(market_id="0xabc", max_size=100.0)
        cfg = LimitsConfig(positions=[pl])
        mgr = LimitsManager(cfg)
        assert mgr.check_position_size("0xabc", 50.0) is True

    def test_check_position_size_exceeds_limit(self):
        pl = PositionLimit(market_id="0xabc", max_size=100.0)
        cfg = LimitsConfig(positions=[pl])
        mgr = LimitsManager(cfg)
        assert mgr.check_position_size("0xabc", 150.0) is False

    def test_check_position_size_below_min(self):
        pl = PositionLimit(market_id="0xabc", max_size=100.0, min_size=10.0)
        cfg = LimitsConfig(positions=[pl])
        mgr = LimitsManager(cfg)
        assert mgr.check_position_size("0xabc", 5.0) is False

    def test_check_position_size_no_specific_limit(self):
        cfg = LimitsConfig()
        mgr = LimitsManager(cfg)
        assert mgr.check_position_size("unknown_market", 9999.0) is True

    def test_check_order_rate_within_limit(self):
        cfg = LimitsConfig(order_rate=OrderRateLimit(max_orders_per_window=5))
        mgr = LimitsManager(cfg)
        assert mgr.check_order_rate(3) is True
        assert mgr.check_order_rate(5) is True

    def test_check_order_rate_exceeds_limit(self):
        cfg = LimitsConfig(order_rate=OrderRateLimit(max_orders_per_window=5))
        mgr = LimitsManager(cfg)
        assert mgr.check_order_rate(6) is False

    def test_check_daily_loss_within_limit(self):
        cfg = LimitsConfig(daily_loss=DailyLossLimit(max_loss_amount=500.0))
        mgr = LimitsManager(cfg)
        assert mgr.check_daily_loss(100.0, -50.0) is True
        assert mgr.check_daily_loss(500.0, 0.0) is True

    def test_check_daily_loss_exceeds_limit(self):
        cfg = LimitsConfig(daily_loss=DailyLossLimit(max_loss_amount=500.0))
        mgr = LimitsManager(cfg)
        assert mgr.check_daily_loss(400.0, -200.0) is False

    def test_check_exposure_within_limit(self):
        cfg = LimitsConfig(exposure=ExposureLimit(max_total_exposure=1000.0))
        mgr = LimitsManager(cfg)
        assert mgr.check_exposure(200.0, 300.0) is True

    def test_check_exposure_exceeds_total(self):
        cfg = LimitsConfig(exposure=ExposureLimit(max_total_exposure=1000.0))
        mgr = LimitsManager(cfg)
        assert mgr.check_exposure(800.0, 300.0) is False

    def test_check_exposure_exceeds_per_market_pct(self):
        cfg = LimitsConfig(
            exposure=ExposureLimit(max_total_exposure=1000.0, max_per_market_pct=10.0)
        )
        mgr = LimitsManager(cfg)
        assert mgr.check_exposure(0.0, 200.0) is False

    def test_check_all_returns_empty_when_all_pass(self):
        pl = PositionLimit(market_id="0xabc", max_size=100.0)
        cfg = LimitsConfig(
            positions=[pl],
            order_rate=OrderRateLimit(max_orders_per_window=10),
            daily_loss=DailyLossLimit(max_loss_amount=500.0),
            exposure=ExposureLimit(max_total_exposure=1000.0),
        )
        mgr = LimitsManager(cfg)
        result = mgr.check_all(
            market_id="0xabc",
            size=50.0,
            order_count=3,
            current_loss=100.0,
            exposure=200.0,
        )
        assert result == []

    def test_check_all_returns_failed_checks(self):
        pl = PositionLimit(market_id="0xabc", max_size=50.0)
        cfg = LimitsConfig(
            positions=[pl],
            order_rate=OrderRateLimit(max_orders_per_window=2),
            daily_loss=DailyLossLimit(max_loss_amount=100.0),
            exposure=ExposureLimit(max_total_exposure=500.0),
        )
        mgr = LimitsManager(cfg)
        result = mgr.check_all(
            market_id="0xabc",
            size=100.0,
            order_count=5,
            current_loss=200.0,
            exposure=600.0,
        )
        assert "position_size_exceeded:0xabc" in result
        assert "order_rate_exceeded" in result
        assert "daily_loss_exceeded" in result
        assert "exposure_exceeded" in result
