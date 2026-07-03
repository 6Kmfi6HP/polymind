"""Shared fixtures for integration tests."""

from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio

from polymind.core.intents import OrderIntent, OrderSide
from polymind.execution.executor import PaperExecutor
from polymind.execution.fill_model import FillModel, FillModelConfig, MarketSnapshot
from polymind.risk.limits import (
    DailyLossLimit,
    ExposureLimit,
    LimitsConfig,
    LimitsManager,
    OrderRateLimit,
    PositionLimit,
)
from polymind.storage.database import DatabaseConfig
from polymind.storage.ledger import LedgerStore
from polymind.storage.price_store import PriceStore


@pytest.fixture
def market_snapshot() -> MarketSnapshot:
    """Standard MarketSnapshot for fill simulation tests."""
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
def order_intent() -> OrderIntent:
    """Standard OrderIntent for execution tests."""
    return OrderIntent(
        market_id="0xabc",
        side=OrderSide.BUY,
        price=0.50,
        size=100.0,
    )


@pytest.fixture
def fill_model() -> FillModel:
    """Standard FillModel with default (PASSIVE) configuration."""
    return FillModel(FillModelConfig())


@pytest.fixture
def paper_executor(fill_model: FillModel) -> PaperExecutor:
    """Pre-configured PaperExecutor with 10_000 initial cash."""
    return PaperExecutor(fill_model=fill_model, initial_cash=10_000.0)


@pytest.fixture
def limits_manager() -> LimitsManager:
    """Relaxed LimitsManager with generous limits for integration testing."""
    config = LimitsConfig(
        positions=[
            PositionLimit(
                market_id="0xabc",
                max_size=1_000.0,
                max_notional=500.0,
                min_size=1.0,
            ),
        ],
        order_rate=OrderRateLimit(
            max_orders_per_window=100,
            window_seconds=60,
        ),
        daily_loss=DailyLossLimit(
            max_loss_amount=1_000.0,
            max_loss_pct=0.10,
        ),
        exposure=ExposureLimit(
            max_total_exposure=5_000.0,
            max_per_market_pct=0.30,
        ),
    )
    return LimitsManager(config)


@pytest_asyncio.fixture
async def ledger_store() -> LedgerStore:
    """In-memory LedgerStore backed by :memory: SQLite."""
    store = LedgerStore(DatabaseConfig(path=":memory:"))
    yield store
    await store.close()


@pytest.fixture
def price_store() -> PriceStore:
    """In-memory PriceStore (path=None operates in memory)."""
    return PriceStore(path=None)
