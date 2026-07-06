"""
Tests for BaseMMStrategy with the ADR 0002 intent migration.
"""

from datetime import datetime, timezone
from typing import Any

import pytest

from polymind.core.intents import (
    CancelIntent,
    OrderIntent,
    OrderSide,
    StrategyIntent,
)
from polymind.core.strategy import BaseMMStrategy, StrategyConfig, StrategySignal


class TestBaseMMStrategy:
    """Strategy base should produce StrategyIntent via analyze()."""

    @pytest.mark.asyncio
    async def test_analyze_returns_none_by_default(self):
        """A strategy that returns None produces no action."""
        strategy = NoopStrategy()
        result = await strategy.analyze("market")
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_returns_strategy_intent(self):
        strategy = PlaceOrderStrategy(config=StrategyConfig(name="place-test"))
        result = await strategy.analyze("market")

        assert isinstance(result, StrategyIntent)
        assert result.strategy_name == "place-test"
        assert len(result.orders) == 1
        assert result.orders[0].side == OrderSide.BUY
        assert result.orders[0].price == 0.50

    @pytest.mark.asyncio
    async def test_analyze_to_signal_converts_order_intent(self):
        strategy = PlaceOrderStrategy()
        signal = await strategy.analyze_to_signal("market")

        assert isinstance(signal, StrategySignal)
        assert signal.action == "place"
        assert signal.market_id == "0x111"
        assert signal.side == "BUY"
        assert signal.price == 0.50

    @pytest.mark.asyncio
    async def test_analyze_to_signal_empty_intent_returns_none(self):
        strategy = EmptyIntentStrategy()
        signal = await strategy.analyze_to_signal("market")
        assert signal is None

    @pytest.mark.asyncio
    async def test_analyze_to_signal_cancel_only_returns_hold(self):
        strategy = CancelOnlyStrategy()
        signal = await strategy.analyze_to_signal("market")

        assert isinstance(signal, StrategySignal)
        assert signal.action == "hold"
        assert signal.market_id == "0x222"

    @pytest.mark.asyncio
    async def test_strategy_config_default_name(self):
        strategy = NoopStrategy()
        assert strategy.name == "NoopStrategy"
        assert strategy.config.name == "NoopStrategy"

    @pytest.mark.asyncio
    async def test_get_config_summary(self):
        strategy = PlaceOrderStrategy(config=StrategyConfig(name="custom", params={"spread": 0.1}))
        summary = strategy.get_config_summary()
        assert summary["strategy"] == "custom"
        assert summary["params"]["spread"] == 0.1

    @pytest.mark.asyncio
    async def test_risk_check_default(self):
        strategy = NoopStrategy()
        assert await strategy.risk_check() is True

    @pytest.mark.asyncio
    async def test_filter_markets_default(self):
        """Default filter_markets returns all markets unchanged."""
        strategy = NoopStrategy()
        markets = ["mkt1", "mkt2", "mkt3"]
        result = strategy.filter_markets(markets)
        assert result == markets

    @pytest.mark.asyncio
    async def test_filter_markets_custom(self):
        """Custom filter_markets on concrete strategy."""
        strategy = FilterOnlyStrategy(allowed={"allowed_market"})
        all_markets = ["mkt1", "allowed_market", "mkt2"]
        result = strategy.filter_markets(all_markets)
        assert result == ["allowed_market"]

    @pytest.mark.asyncio
    async def test_filter_markets_empty(self):
        """filter_markets returns empty list when nothing passes."""
        strategy = FilterOnlyStrategy(allowed=set())
        result = strategy.filter_markets(["mkt1", "mkt2"])
        assert result == []

    @pytest.mark.asyncio
    async def test_strategy_with_filter_markets_in_engine(self):
        """filter_markets is called before analyze in TradingEngine.run_tick_all."""
        from datetime import datetime
        from unittest.mock import AsyncMock

        from polymind.core.engine import TradingEngine, TradingEngineConfig
        from polymind.core.intents import IntentExecutor
        from polymind.execution.fill_model import MarketSnapshot

        strategy = FilterOnlyStrategy(allowed={"mkt2"})
        executor = AsyncMock(spec=IntentExecutor)
        executor.execute = AsyncMock(return_value={})
        engine = TradingEngine(
            strategy=strategy,
            executor=executor,
            config=TradingEngineConfig(strategy_name="test"),
        )

        snapshots = [
            MarketSnapshot(
                market_id="mkt1",
                timestamp=datetime(2026, 7, 4),
                bid_price=0.5,
                ask_price=0.6,
                mid_price=0.55,
                bid_size=100,
                ask_size=100,
            ),
            MarketSnapshot(
                market_id="mkt2",
                timestamp=datetime(2026, 7, 4),
                bid_price=0.5,
                ask_price=0.6,
                mid_price=0.55,
                bid_size=100,
                ask_size=100,
            ),
        ]

        results = await engine.run_tick_all(snapshots)
        assert len(results) == 1  # only mkt2 passed the filter
        assert results[0].strategy == "test"


# ── Concrete strategy stubs for testing ──────────────────────────────────


class NoopStrategy(BaseMMStrategy):
    """Always returns None (no action)."""

    async def analyze(self, market: Any) -> StrategyIntent | None:
        return None


class PlaceOrderStrategy(BaseMMStrategy):
    """Always returns a single BUY order intent."""

    async def analyze(self, market: Any) -> StrategyIntent | None:
        now = datetime.now(timezone.utc)
        order = OrderIntent(
            market_id="0x111",
            side=OrderSide.BUY,
            price=0.50,
            size=10.0,
        )
        return StrategyIntent(timestamp=now, strategy_name=self.name, orders=[order])


class EmptyIntentStrategy(BaseMMStrategy):
    """Returns an empty StrategyIntent (no orders, no cancels)."""

    async def analyze(self, market: Any) -> StrategyIntent | None:
        now = datetime.now(timezone.utc)
        return StrategyIntent(timestamp=now, strategy_name=self.name)


class CancelOnlyStrategy(BaseMMStrategy):
    """Only produces a cancel intent, no orders."""

    async def analyze(self, market: Any) -> StrategyIntent | None:
        now = datetime.now(timezone.utc)
        cancel = CancelIntent(market_id="0x222", reason="reprice")
        return StrategyIntent(timestamp=now, strategy_name=self.name, cancels=[cancel])


class FilterOnlyStrategy(BaseMMStrategy):
    """Strategy that filters markets to a specific set (REF-001d)."""

    def __init__(self, allowed: set[str] | None = None):
        super().__init__(config=StrategyConfig(name="FilterOnly"))
        self._allowed = allowed or set()

    def filter_markets(self, markets: list[Any]) -> list[Any]:
        return [m for m in markets if self._is_allowed(m)]

    def _is_allowed(self, market: Any) -> bool:
        mid = market if isinstance(market, str) else getattr(market, "market_id", "")
        return mid in self._allowed

    async def analyze(self, market: Any) -> StrategyIntent | None:
        return None
