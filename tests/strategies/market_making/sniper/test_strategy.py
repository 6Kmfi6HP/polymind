"""
Tests for SniperStrategy — deep-discount limit order strategy.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.strategy import StrategyConfig
from polymind.execution.fill_model import MarketSnapshot
from polymind.strategies.market_making.sniper.strategy import (
    SniperConfig,
    SniperStrategy,
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
def strategy() -> SniperStrategy:
    cfg = SniperConfig(discount_threshold=0.5, order_size=20.0)
    return SniperStrategy(
        config=StrategyConfig(name="sniper"),
        mm_config=cfg,
    )


class TestSniperStrategy:
    async def test_discount_triggered_places_order(self, strategy: SniperStrategy):
        """ask=0.25, mid=0.50 => discount=50% => trigger buy."""
        market = MarketSnapshot(
            market_id="mkt1",
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            bid_price=0.45,
            ask_price=0.25,
            mid_price=0.50,
            bid_size=1000.0,
            ask_size=1000.0,
        )
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.orders) == 1
        assert intent.orders[0].side.value == "BUY"
        assert intent.orders[0].size == 20.0
        assert intent.orders[0].price == 0.25

    async def test_no_discount_returns_empty(self, strategy: SniperStrategy):
        """ask=0.48, mid=0.50 => discount=4% => no buy."""
        market = _snapshot(bid=0.46, ask=0.48)
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.orders) == 0

    async def test_invalid_prices_returns_none(self, strategy: SniperStrategy):
        market = _snapshot(bid=0.0, ask=0.0)
        intent = await strategy.analyze(market)
        assert intent is None

    async def test_cancel_on_every_tick(self, strategy: SniperStrategy):
        market = _snapshot(bid=0.46, ask=0.48)
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.cancels) == 1

    async def test_config_defaults(self):
        cfg = SniperConfig()
        assert cfg.discount_threshold == 0.50
        assert cfg.order_size == 20.0
        assert cfg.max_position == 200.0

    async def test_manual_fair_value(self):
        cfg = SniperConfig(
            discount_threshold=0.5,
            fair_value_source="manual",
            manual_fair_value=1.0,
        )
        strat = SniperStrategy(
            config=StrategyConfig(name="sniper"),
            mm_config=cfg,
        )
        # ask=0.60, fv=1.0 => discount=40% < 50% => no buy
        market = _snapshot(bid=0.55, ask=0.60)
        intent = await strat.analyze(market)
        assert intent is not None
        assert len(intent.orders) == 0
