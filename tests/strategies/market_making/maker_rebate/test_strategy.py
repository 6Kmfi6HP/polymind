"""
Tests for MakerRebateStrategy — YES+NO price arbitrage logic.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.strategy import StrategyConfig
from polymind.execution.fill_model import MarketSnapshot
from polymind.strategies.market_making.maker_rebate.strategy import (
    MakerRebateConfig,
    MakerRebateStrategy,
)


def _snapshot(
    market_id: str = "mkt1",
    bid: float = 0.45,
    ask: float = 0.55,
    outcomes: dict | None = None,
) -> MarketSnapshot:
    """Build a MarketSnapshot with optional outcomes via extra fields."""
    snap = MarketSnapshot(
        market_id=market_id,
        timestamp=datetime(2026, 7, 4, 12, 0, 0),
        bid_price=bid,
        ask_price=ask,
        mid_price=(bid + ask) / 2,
        bid_size=1000.0,
        ask_size=1000.0,
    )
    if outcomes is not None:
        snap.outcomes = outcomes  # type: ignore[attr-defined]
    return snap


@pytest.fixture
def strategy() -> MakerRebateStrategy:
    cfg = MakerRebateConfig(rebate_threshold=0.01, order_size=10.0)
    return MakerRebateStrategy(
        config=StrategyConfig(name="maker_rebate"),
        mm_config=cfg,
    )


class TestMakerRebateStrategy:
    """Tests for MakerRebateStrategy analysis logic."""

    async def test_rebate_opportunity_places_orders(self, strategy: MakerRebateStrategy):
        """YES=0.45, NO=0.45 → sum=0.90, rebate=0.10 > threshold"""
        market = _snapshot(
            outcomes={
                "YES": {"ask_price": 0.45, "bid_price": 0.40},
                "NO": {"ask_price": 0.45, "bid_price": 0.40},
            },
        )
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.orders) == 2
        assert all(o.side.value == "BUY" for o in intent.orders)
        assert intent.orders[0].outcome == "YES"
        assert intent.orders[1].outcome == "NO"
        assert intent.orders[0].size == 10.0
        assert intent.orders[1].size == 10.0

    async def test_invalid_prices_returns_none(self, strategy: MakerRebateStrategy):
        """Zero bid/ask should return None."""
        market = _snapshot(bid=0.0, ask=0.0)
        intent = await strategy.analyze(market)
        assert intent is None

    async def test_outcomes_fallback_to_top_level(self, strategy: MakerRebateStrategy):
        """Without outcomes dict, fall back to top-level ask_price."""
        market = _snapshot(bid=0.48, ask=0.52)
        # Without a NO ask, it won't place both orders
        intent = await strategy.analyze(market)
        assert intent is None or len(intent.orders) == 0

    async def test_rebate_below_threshold(self, strategy: MakerRebateStrategy):
        """sum=0.995, rebate=0.005 < threshold=0.01 → no buy orders."""
        strategy.mm_config.rebate_threshold = 0.01
        market = _snapshot(
            outcomes={
                "YES": {"ask_price": 0.495, "bid_price": 0.49},
                "NO": {"ask_price": 0.50, "bid_price": 0.49},
            },
        )
        intent = await strategy.analyze(market)
        if intent is not None:
            assert all(o.side.value == "SELL" for o in intent.orders)

    async def test_cancel_refresh_on_every_tick(self, strategy: MakerRebateStrategy):
        """Each tick should include a cancel-all intent."""
        market = _snapshot(
            outcomes={
                "YES": {"ask_price": 0.45, "bid_price": 0.40},
                "NO": {"ask_price": 0.45, "bid_price": 0.40},
            },
        )
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.cancels) == 1
        assert intent.cancels[0].market_id == "mkt1"

    async def test_config_defaults(self):
        """Test default config values."""
        cfg = MakerRebateConfig()
        assert cfg.max_spread == 0.03
        assert cfg.order_size == 10.0
        assert cfg.merge_on_fill is True
        assert cfg.price_tolerance == 0.001
        assert cfg.rebate_threshold == 0.005

    async def test_strategy_has_correct_name(self, strategy: MakerRebateStrategy):
        assert strategy.name == "maker_rebate"
