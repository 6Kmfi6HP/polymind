"""Risk manager safety contracts."""

import pytest

from polymind.core.config import RiskLimits
from polymind.risk.manager import RiskManager


def test_risk_manager_starts_with_mutable_trade_history():
    manager = RiskManager(initial_capital=1_000)

    assert isinstance(manager.trades, list)

    manager.record_trade(size=10, price=0.40)

    assert len(manager.trades) == 1
    assert manager.to_dict()["trade_count"] == 1


@pytest.mark.parametrize(
    ("size", "price", "reason"),
    [
        (51, 0.50, "single position size exceeds max_position_size"),
        (25, 0.81, "new notional exposure exceeds max_total_exposure"),
    ],
)
def test_risk_manager_rejects_positions_that_exceed_configured_limits(size, price, reason):
    limits = RiskLimits(max_position_size=50, max_total_exposure=20, max_daily_loss=100)
    manager = RiskManager(initial_capital=1_000, limits=limits)

    assert manager.can_open_position(size=10, price=0.50), "sanity check: within configured limits"
    assert not manager.can_open_position(size=size, price=price), reason


def test_risk_manager_rejects_positions_after_configured_daily_loss_is_hit():
    limits = RiskLimits(max_position_size=50, max_total_exposure=100, max_daily_loss=25)
    manager = RiskManager(initial_capital=1_000, limits=limits)

    manager.record_trade(size=10, price=0.50, pnl=-25.01)

    assert not manager.can_open_position(size=1, price=0.50)
