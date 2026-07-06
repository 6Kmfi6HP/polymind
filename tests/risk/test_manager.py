"""
Tests for RiskManager.
"""

from __future__ import annotations

import pytest

from polymind.risk.manager import RiskManager


class TestRiskManager:
    def test_initial_capital(self):
        rm = RiskManager(initial_capital=10_000.0)
        assert rm.initial_capital == 10_000.0
        assert rm.current_capital == 10_000.0

    def test_initial_capital_must_be_positive(self):
        with pytest.raises(ValueError, match="positive"):
            RiskManager(initial_capital=0)

    # ── Kelly sizing ──────────────────────────────────────────────────────

    def test_kelly_sizing(self):
        rm = RiskManager(initial_capital=10_000.0)
        size = rm.calculate_position_size(
            price=0.5, confidence=0.6, method="kelly", kelly_fraction=0.25
        )
        assert size >= 0
        assert size <= rm.current_capital * 0.25 / 0.5  # max possible

    def test_kelly_high_confidence(self):
        rm = RiskManager(1000.0)
        size = rm.calculate_position_size(price=0.5, confidence=0.9, method="kelly")
        assert size > 0

    def test_kelly_low_confidence(self):
        rm = RiskManager(1000.0)
        size = rm.calculate_position_size(price=0.5, confidence=0.1, method="kelly")
        assert size == 0

    def test_manual_method_returns_zero(self):
        rm = RiskManager(1000.0)
        size = rm.calculate_position_size(price=0.5, method="manual")
        assert size == 0

    # ── Fixed percentage sizing (REF-001c) ────────────────────────────────

    def test_fixed_pct_sizing(self):
        rm = RiskManager(1000.0, position_size_pct=0.05)
        size = rm.calculate_position_size(price=0.5, method="fixed_pct")
        expected = 1000.0 * 0.05 / 0.5  # 100 shares
        assert size == pytest.approx(expected)

    def test_fixed_pct_low_capital(self):
        rm = RiskManager(100.0, position_size_pct=0.1)
        size = rm.calculate_position_size(price=0.8, method="fixed_pct")
        expected = 100.0 * 0.1 / 0.8  # 12.5 shares
        assert size == pytest.approx(expected)

    # ── Confidence-based sizing (REF-001c) ────────────────────────────────

    def test_confidence_based_sizing_full(self):
        rm = RiskManager(1000.0, position_size_pct=0.1)
        size = rm.calculate_position_size(price=0.5, confidence=1.0, method="confidence_based")
        # 1000 * 0.1 * 1.0 / 0.5 = 200
        assert size == pytest.approx(200.0)

    def test_confidence_based_sizing_half(self):
        rm = RiskManager(1000.0, position_size_pct=0.1)
        size = rm.calculate_position_size(price=0.5, confidence=0.5, method="confidence_based")
        # 1000 * 0.1 * 0.5 / 0.5 = 100
        assert size == pytest.approx(100.0)

    def test_confidence_based_zero_confidence(self):
        rm = RiskManager(1000.0)
        size = rm.calculate_position_size(price=0.5, confidence=0.0, method="confidence_based")
        assert size == 0.0

    # ── Dynamic multi-factor sizing (REF-001c) ────────────────────────────

    def test_dynamic_sizing_defaults(self):
        rm = RiskManager(1000.0, position_size_pct=0.05)
        size = rm.calculate_position_size(price=0.5, confidence=0.5, method="dynamic")
        # conf=0.5 → factor=1.0, vol=0.5 → factor=0.9, streak=0 → factor=1.0, perf=1.0, cap=1.0
        # combined = 1.0 * 0.9 * 1.0 * 1.0 * 1.0 = 0.9
        # adjusted_pct = 0.05 * 0.9 = 0.045 → within [0.01, 0.20]
        # position_value = 1000 * 0.045 = 45 → size = 45 / 0.5 = 90
        assert size == pytest.approx(90.0, rel=0.01)

    def test_dynamic_size_increases_with_streak(self):
        rm = RiskManager(1000.0, position_size_pct=0.05)
        size_hot = rm.calculate_position_size(
            price=0.5, confidence=0.5, method="dynamic", win_streak=5
        )
        size_cold = rm.calculate_position_size(
            price=0.5, confidence=0.5, method="dynamic", lose_streak=3
        )
        assert size_hot > size_cold

    def test_dynamic_size_reduced_by_volatility(self):
        rm = RiskManager(1000.0, position_size_pct=0.05)
        size_low_vol = rm.calculate_position_size(
            price=0.5, confidence=0.5, method="dynamic", volatility=0.2
        )
        size_high_vol = rm.calculate_position_size(
            price=0.5, confidence=0.5, method="dynamic", volatility=0.8
        )
        assert size_low_vol > size_high_vol

    def test_dynamic_size_clamped(self):
        rm = RiskManager(1000.0, position_size_pct=0.05)
        size = rm.calculate_position_size(
            price=0.5,
            confidence=1.0,
            method="dynamic",
            volatility=0.0,
            win_streak=10,
        )
        # clamping keeps size reasonable
        max_possible = 1000.0 * 0.20 / 0.5  # 400
        assert size <= max_possible

    # ── can_open_position ─────────────────────────────────────────────────

    def test_can_open_position(self):
        rm = RiskManager(1000.0)
        assert rm.can_open_position(50.0, 0.5) is True
        # 300 shares @ 0.5 = $150 → 15% of capital, exceeds 10%
        assert rm.can_open_position(300.0, 0.5) is False

    def test_can_open_position_exact_boundary(self):
        rm = RiskManager(1000.0)
        # 200 shares @ 0.5 = $100 = exactly 10% of capital → boundary allowed
        assert rm.can_open_position(200.0, 0.5) is True

    # ── Stop-loss (REF-001c) ─────────────────────────────────────────────

    def test_stop_loss_triggered(self):
        rm = RiskManager(1000.0, default_stop_loss_pct=0.05)
        assert rm.should_stop_loss(entry_price=0.50, current_price=0.46, size=100.0) is True

    def test_stop_loss_not_triggered(self):
        rm = RiskManager(1000.0, default_stop_loss_pct=0.05)
        assert rm.should_stop_loss(entry_price=0.50, current_price=0.48, size=100.0) is False

    def test_stop_loss_profit_does_not_trigger(self):
        rm = RiskManager(1000.0)
        # Price went up — no stop-loss
        assert rm.should_stop_loss(entry_price=0.50, current_price=0.60, size=100.0) is False

    def test_stop_loss_custom_threshold(self):
        rm = RiskManager(1000.0)
        # At 10% loss with a 15% threshold — no trigger
        assert (
            rm.should_stop_loss(
                entry_price=0.50, current_price=0.45, size=100.0, stop_loss_pct=0.15
            )
            is False
        )
        # At 10% loss with a 5% threshold — trigger
        assert (
            rm.should_stop_loss(
                entry_price=0.50, current_price=0.45, size=100.0, stop_loss_pct=0.05
            )
            is True
        )

    # ── Take-profit (REF-001c) ────────────────────────────────────────────

    def test_take_profit_triggered(self):
        rm = RiskManager(1000.0, default_take_profit_pct=0.15)
        assert rm.should_take_profit(entry_price=0.50, current_price=0.58, size=100.0) is True

    def test_take_profit_not_triggered(self):
        rm = RiskManager(1000.0, default_take_profit_pct=0.15)
        assert rm.should_take_profit(entry_price=0.50, current_price=0.54, size=100.0) is False

    def test_take_profit_loss_does_not_trigger(self):
        rm = RiskManager(1000.0)
        assert rm.should_take_profit(entry_price=0.50, current_price=0.40, size=100.0) is False

    def test_take_profit_custom_threshold(self):
        rm = RiskManager(1000.0)
        assert (
            rm.should_take_profit(
                entry_price=0.50, current_price=0.55, size=100.0, take_profit_pct=0.05
            )
            is True
        )
        assert (
            rm.should_take_profit(
                entry_price=0.50, current_price=0.55, size=100.0, take_profit_pct=0.15
            )
            is False
        )

    # ── Trade recording (enhanced) ────────────────────────────────────────

    def test_record_trade(self):
        rm = RiskManager(1000.0)
        rm.record_trade(10.0, 0.5)
        assert len(rm.trades) == 1

    def test_record_trade_updates_capital(self):
        rm = RiskManager(1000.0)
        rm.record_trade(10.0, 0.5, pnl=25.0)
        assert rm.current_capital == 1025.0
        assert rm._daily_pnl == 25.0

    def test_record_trade_updates_peak(self):
        rm = RiskManager(1000.0)
        rm.record_trade(10.0, 0.5, pnl=50.0)
        assert rm.peak_capital == 1050.0

    # ── to_dict ───────────────────────────────────────────────────────────

    def test_to_dict(self):
        rm = RiskManager(5000.0)
        d = rm.to_dict()
        assert d["initial_capital"] == 5000.0
        assert d["trade_count"] == 0
        assert d["position_size_pct"] == 0.05
