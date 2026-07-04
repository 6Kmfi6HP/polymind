"""
Tests for CopyTradeStrategy — wallet trade replication.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.strategy import StrategyConfig
from polymind.execution.fill_model import MarketSnapshot
from polymind.strategies.market_making.copy_trade.strategy import (
    CopyTradeConfig,
    CopyTradeStrategy,
    TrackedTrade,
)


def _snapshot(market_id: str = "mkt1") -> MarketSnapshot:
    return MarketSnapshot(
        market_id=market_id,
        timestamp=datetime(2026, 7, 4, 12, 0, 0),
        bid_price=0.45,
        ask_price=0.55,
        mid_price=0.50,
        bid_size=1000.0,
        ask_size=1000.0,
    )


@pytest.fixture
def strategy() -> CopyTradeStrategy:
    cfg = CopyTradeConfig(
        target_wallet="0xtarget",
        allocation_ratio=0.5,
        min_trade_size=1.0,
        max_trade_size=50.0,
    )
    return CopyTradeStrategy(
        config=StrategyConfig(name="copy_trade"),
        mm_config=cfg,
    )


class TestCopyTradeStrategy:
    async def test_no_pending_trades_returns_none(self, strategy: CopyTradeStrategy):
        market = _snapshot()
        intent = await strategy.analyze(market)
        assert intent is None

    async def test_replicates_trade(self, strategy: CopyTradeStrategy):
        trade = TrackedTrade(
            market_id="mkt1",
            side="BUY",
            price=0.52,
            size=20.0,
            outcome="YES",
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            tx_hash="0xabc123",
        )
        strategy.add_trade(trade)

        market = _snapshot()
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.orders) == 1
        assert intent.orders[0].side.value == "BUY"
        assert intent.orders[0].size == 10.0  # 20 * 0.5 ratio
        assert intent.orders[0].outcome == "YES"

    async def test_deduplicates_trades(self, strategy: CopyTradeStrategy):
        trade = TrackedTrade(
            market_id="mkt1",
            side="BUY",
            price=0.52,
            size=20.0,
            outcome="YES",
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            tx_hash="0xabc123",
        )
        strategy.add_trade(trade)
        strategy.add_trade(trade)  # duplicate

        market = _snapshot()
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.orders) == 1  # deduped

    async def test_size_capped_by_max(self, strategy: CopyTradeStrategy):
        trade = TrackedTrade(
            market_id="mkt1",
            side="SELL",
            price=0.52,
            size=200.0,
            outcome="NO",
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            tx_hash="0xdef456",
        )
        strategy.add_trade(trade)

        market = _snapshot()
        intent = await strategy.analyze(market)
        assert intent is not None
        assert len(intent.orders) == 1
        # 200 * 0.5 = 100 → capped at max_trade_size=50
        assert intent.orders[0].size == 50.0

    async def test_filter_by_market(self, strategy: CopyTradeStrategy):
        trade = TrackedTrade(
            market_id="different_market",
            side="BUY",
            price=0.52,
            size=20.0,
            outcome="YES",
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            tx_hash="0xghi789",
        )
        strategy.add_trade(trade)

        market = _snapshot()
        intent = await strategy.analyze(market)
        assert intent is None  # trade not for this market

    async def test_config_defaults(self):
        cfg = CopyTradeConfig()
        assert cfg.allocation_ratio == 0.1
        assert cfg.min_trade_size == 1.0
        assert cfg.max_trade_size == 100.0

    async def test_tracked_trade_default_tx_hash(self):
        trade = TrackedTrade(
            market_id="mkt1",
            side="BUY",
            price=0.5,
            size=10.0,
            outcome="YES",
            timestamp=datetime(2026, 7, 4),
        )
        assert trade.tx_hash == ""
