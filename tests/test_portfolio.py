"""
Tests for PortfolioTarget and PositionDirection.
"""

from __future__ import annotations

from polymind.core.portfolio import PortfolioTarget, PositionDirection


class TestPositionDirection:
    def test_enum_values_present(self):
        assert PositionDirection.LONG.value == 1
        assert PositionDirection.SHORT.value == 2
        assert PositionDirection.NEUTRAL.value == 3

    def test_enum_inequality(self):
        assert PositionDirection.LONG != PositionDirection.SHORT


class TestPortfolioTarget:
    def test_minimal_construction(self):
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=100.0,
            confidence=0.75,
            rank=1,
        )
        assert target.market_id == "0xabc"
        assert target.direction == PositionDirection.LONG
        assert target.target_size == 100.0
        assert target.confidence == 0.75
        assert target.rank == 1
        assert target.holding_period_hours is None
        assert target.reason == ""

    def test_full_construction(self):
        target = PortfolioTarget(
            market_id="0xdef",
            direction=PositionDirection.SHORT,
            target_size=50.0,
            confidence=0.3,
            rank=9,
            holding_period_hours=24.0,
            reason="weak momentum signal",
            metadata={"signal_id": "mom_7d"},
        )
        assert target.holding_period_hours == 24.0
        assert target.reason == "weak momentum signal"
        assert target.metadata["signal_id"] == "mom_7d"

    def test_neutral_direction(self):
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.NEUTRAL,
            target_size=0.0,
            confidence=0.5,
            rank=5,
        )
        assert target.direction == PositionDirection.NEUTRAL
        assert target.target_size == 0.0
