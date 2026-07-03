"""Shared fixtures for integration tests."""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.intents import OrderIntent, OrderSide
from polymind.execution.executor import PaperExecutor
from polymind.execution.fill_model import FillModel, FillModelConfig, FillMode, MarketSnapshot
from polymind.risk.manager import RiskManager
from polymind.risk.limits import LimitsConfig, LimitsManager, PositionLimit, OrderRateLimit, DailyLossLimit, ExposureLimit


@pytest.fixture
def market_snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        market_id="0xabc",
        bid_price=0.50,
        bid_size=1000.0,
        ask_price=0.51,
        ask_size=1000.0,
        mid_price=0.505,
        timestamp=datetime(2026, 1, 1),
    )


@pytest.fixture
def fill_model() -> FillModel:
    return FillModel(FillModelConfig(mode=FillMode.TAKER))


@pytest.fixture
def paper_executor(fill_model: FillModel) -> PaperExecutor:
    return PaperExecutor(fill_model=fill_model, initial_cash=10_000.0)


@pytest.fixture
def risk_manager() -> RiskManager:
    return RiskManager(max_risk_per_trade=0.02, max_portfolio_risk=0.10)


@pytest.fixture
def limits_manager() -> LimitsManager:
    config = LimitsConfig(
        positions=[PositionLimit(market_id="0xabc", max_size=1000.0, max_notional=500.0, min_size=1.0)],
        order_rate=OrderRateLimit(max_orders_per_window=100, window_seconds=60),
        daily_loss=DailyLossLimit(max_loss_amount=1000.0, max_loss_pct=0.10),
        exposure=ExposureLimit(max_total_exposure=5000.0, max_per_market_pct=0.30),
    )
    return LimitsManager(config)
