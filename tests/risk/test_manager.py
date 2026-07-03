"""
Tests for RiskManager.
"""

from __future__ import annotations

from polymind.risk.manager import RiskManager


class TestRiskManager:
    def test_initial_capital(self):
        rm = RiskManager(initial_capital=10_000.0)
        assert rm.initial_capital == 10_000.0
        assert rm.current_capital == 10_000.0

    def test_kelly_sizing(self):
        rm = RiskManager(initial_capital=10_000.0)
        size = rm.calculate_position_size(price=0.5, confidence=0.6, method="kelly")
        assert size >= 0
        assert size <= rm.current_capital

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

    def test_can_open_position(self):
        rm = RiskManager(1000.0)
        assert rm.can_open_position(50.0, 0.5) is True
        assert rm.can_open_position(200.0, 0.5) is False  # > 10% of capital

    def test_record_trade(self):
        rm = RiskManager(1000.0)
        rm.record_trade(10.0, 0.5)
        assert len(rm.trades) == 1

    def test_to_dict(self):
        rm = RiskManager(5000.0)
        d = rm.to_dict()
        assert d["initial_capital"] == 5000.0
        assert d["trade_count"] == 0
