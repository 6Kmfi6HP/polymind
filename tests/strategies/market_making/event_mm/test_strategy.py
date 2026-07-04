"""
Tests for EventMMStrategy — event-driven market making.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.strategy import StrategyConfig
from polymind.execution.fill_model import MarketSnapshot
from polymind.strategies.market_making.event_mm.strategy import (
    EventMMConfig,
    EventMMStrategy,
)


def _snapshot(
    market_id: str = "mkt1",
    bid: float = 0.48,
    ask: float = 0.52,
) -> MarketSnapshot:
    return MarketSnapshot(
        market_id=market_id,
        timestamp=datetime(2026, 7, 4, 12, 0, 0),
        bid_price=bid,
        ask_price=ask,
        mid_price=(bid + ask) / 2,
        bid_size=1000.0,
        ask_size=1000.0,
    )


@pytest.fixture
def strategy() -> EventMMStrategy:
    cfg = EventMMConfig(spread_pct=0.05, order_size=10.0, cooldown_seconds=300)
    return EventMMStrategy(
        config=StrategyConfig(name="event_mm"),
        mm_config=cfg,
    )


class TestEventMMStrategy:
    async def test_normal_state_places_both_sides(self, strategy: EventMMStrategy):
        market = _snapshot(bid=0.48, ask=0.52)
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.orders) == 2
        assert intent.orders[0].side.value == "BUY"
        assert intent.orders[1].side.value == "SELL"

    async def test_triggered_state_wider_spread(self, strategy: EventMMStrategy):
        strategy.set_triggered(True)
        market = _snapshot(bid=0.45, ask=0.55)
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.orders) == 2

    async def test_invalid_prices_returns_none(self, strategy: EventMMStrategy):
        market = _snapshot(bid=0.0, ask=0.0)
        intent = await strategy.analyze(market)
        assert intent is None

    async def test_cancel_on_every_tick(self, strategy: EventMMStrategy):
        market = _snapshot()
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.cancels) == 1

    async def test_config_defaults(self):
        cfg = EventMMConfig()
        assert cfg.spread_pct == 0.05
        assert cfg.order_size == 10.0
        assert cfg.cooldown_seconds == 300

    async def test_in_cooldown(self, strategy: EventMMStrategy):
        assert strategy.in_cooldown is False
