"""
Tests for TradingEngine — central orchestrator.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from polymind.core.engine import TradingEngine, TradingEngineConfig
from polymind.core.intents import IntentExecutor, OrderIntent, OrderSide, StrategyIntent
from polymind.core.risk import RiskDecision, RiskGate
from polymind.core.strategy import BaseMMStrategy
from polymind.execution.fill_model import MarketSnapshot
from polymind.workflows.runner import WorkflowRunner


@pytest.fixture
def market() -> MarketSnapshot:
    return MarketSnapshot(
        market_id="mkt1",
        timestamp=datetime(2026, 7, 4, 12, 0, 0),
        bid_price=0.45,
        ask_price=0.55,
        mid_price=0.50,
        bid_size=1000.0,
        ask_size=1000.0,
    )


@pytest.fixture
def strategy() -> AsyncMock:
    s = AsyncMock(spec=BaseMMStrategy)
    s.analyze = AsyncMock()
    s.name = "test_strat"
    return s


@pytest.fixture
def executor() -> AsyncMock:
    e = AsyncMock(spec=IntentExecutor)
    e.execute = AsyncMock(return_value={})
    return e


@pytest.fixture
def runner() -> WorkflowRunner:
    return WorkflowRunner()


@pytest.fixture
def engine(strategy: AsyncMock, executor: AsyncMock) -> TradingEngine:
    cfg = TradingEngineConfig(strategy_name="test_strat")
    return TradingEngine(strategy=strategy, executor=executor, config=cfg)


class TestTradingEngine:
    async def test_run_tick_with_intent(
        self,
        engine: TradingEngine,
        strategy: AsyncMock,
        executor: AsyncMock,
        market: MarketSnapshot,
    ):
        order = OrderIntent(
            market_id="mkt1",
            side=OrderSide.BUY,
            price=0.45,
            size=10.0,
        )
        intent = StrategyIntent(
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            strategy_name="test_strat",
            orders=[order],
        )
        strategy.analyze.return_value = intent
        executor.execute.return_value = {
            "order1": {"status": "OPEN", "order_id": "oid1"},
        }

        result = await engine.run_tick(market)

        assert result.orders_proposed == 1
        assert result.orders_placed == 1
        assert result.risk_approved is True
        assert result.error == ""
        strategy.analyze.assert_called_once()
        executor.execute.assert_called_once()

    async def test_run_tick_empty_intent(
        self,
        engine: TradingEngine,
        strategy: AsyncMock,
        market: MarketSnapshot,
    ):
        strategy.analyze.return_value = None
        result = await engine.run_tick(market)
        assert result.orders_proposed == 0
        assert result.error == ""

    async def test_run_tick_strategy_error(
        self,
        engine: TradingEngine,
        strategy: AsyncMock,
        market: MarketSnapshot,
    ):
        strategy.analyze.side_effect = ValueError("analysis failed")
        result = await engine.run_tick(market)
        assert result.error != ""

    async def test_run_tick_executor_error(
        self,
        engine: TradingEngine,
        strategy: AsyncMock,
        executor: AsyncMock,
        market: MarketSnapshot,
    ):
        order = OrderIntent(market_id="mkt1", side=OrderSide.BUY, price=0.45, size=10.0)
        strategy.analyze.return_value = StrategyIntent(
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            strategy_name="test",
            orders=[order],
        )
        executor.execute.side_effect = RuntimeError("executor error")
        result = await engine.run_tick(market)
        assert result.error != ""

    async def test_risk_gate_rejects(
        self,
        strategy: AsyncMock,
        executor: AsyncMock,
        market: MarketSnapshot,
    ):
        risk = AsyncMock(spec=RiskGate)
        risk.evaluate = AsyncMock(
            return_value=RiskDecision(
                gate_name="test_gate",
                approved=False,
                reason="Position limit exceeded",
            ),
        )
        engine = TradingEngine(
            strategy=strategy,
            executor=executor,
            risk_manager=risk,
        )
        order = OrderIntent(market_id="mkt1", side=OrderSide.BUY, price=0.45, size=100.0)
        strategy.analyze.return_value = StrategyIntent(
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            strategy_name="test",
            orders=[order],
        )

        result = await engine.run_tick(market)
        assert result.risk_approved is False
        assert "Position limit" in result.error

    async def test_status(self, engine: TradingEngine):
        status = engine.status()
        assert status["strategy"] == "test_strat"
        assert status["running"] is False
        assert status["total_ticks"] == 0

    async def test_stop(self, engine: TradingEngine):
        await engine.stop()
        assert engine._running is False

    async def test_start_background(
        self,
        strategy: AsyncMock,
        executor: AsyncMock,
    ):
        engine = TradingEngine(strategy=strategy, executor=executor)
        strategy.analyze.return_value = None
        provider = AsyncMock()
        provider.return_value = MarketSnapshot(
            market_id="mkt1",
            timestamp=datetime(2026, 7, 4),
            bid_price=0.5,
            ask_price=0.6,
            mid_price=0.55,
            bid_size=100.0,
            ask_size=100.0,
        )
        task = engine.start_background(provider)
        assert task is not None
        await engine.stop()
        assert engine._running is False

    async def test_run_forever_stop(
        self,
        strategy: AsyncMock,
        executor: AsyncMock,
    ):
        engine = TradingEngine(
            strategy=strategy,
            executor=executor,
            config=TradingEngineConfig(strategy_name="test", loop_interval=0.01),
        )
        strategy.analyze.return_value = None
        provider = AsyncMock()
        provider.return_value = MarketSnapshot(
            market_id="mkt1",
            timestamp=datetime(2026, 7, 4),
            bid_price=0.5,
            ask_price=0.6,
            mid_price=0.55,
            bid_size=100.0,
            ask_size=100.0,
        )

        async def run_and_stop():
            await asyncio.sleep(0.01)
            await engine.stop()

        loop_task = asyncio.create_task(engine.run_forever(provider))
        await asyncio.sleep(0.05)
        await engine.stop()
        await loop_task
        assert engine._running is False

    # ── New: cover engine edge cases ────────────────────────────────

    async def test_empty_intent_is_empty(self, engine, strategy, market):
        """Empty StrategyIntent with no orders/cancels (line 123-132)."""
        strategy.analyze.return_value = StrategyIntent(
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            strategy_name="test",
            orders=[],
            cancels=[],
        )
        result = await engine.run_tick(market)
        assert result.orders_proposed == 0
        assert result.error == ""

    async def test_exec_result_with_cancelled_status(
        self,
        engine,
        strategy,
        executor,
        market,
    ):
        """Line 177-180: cancelled status counted in orders_cancelled."""
        order = OrderIntent(market_id="mkt1", side=OrderSide.BUY, price=0.45, size=10.0)
        intent = StrategyIntent(
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            strategy_name="test",
            orders=[order],
        )
        strategy.analyze.return_value = intent
        executor.execute.return_value = {
            "mkt1": {"status": "CANCELLED"},
        }
        result = await engine.run_tick(market)
        assert result.orders_cancelled == 1
        assert result.orders_placed == 0

    async def test_exec_result_with_non_dict_values(self, engine, strategy, executor, market):
        """Line 175-176: handle non-dict entries in exec_result."""
        order = OrderIntent(market_id="mkt1", side=OrderSide.BUY, price=0.45, size=10.0)
        intent = StrategyIntent(
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            strategy_name="test",
            orders=[order],
        )
        strategy.analyze.return_value = intent
        executor.execute.return_value = {"mkt1": "some_string"}
        result = await engine.run_tick(market)
        assert result.orders_placed == 0
        assert result.error == ""

    async def test_status_after_ticks(self, engine, strategy, executor, market):
        """status() reflects tick counts (line 244-247)."""
        strategy.analyze.return_value = None
        await engine.run_tick(market)
        await engine.run_tick(market)
        status = engine.status()
        assert status["total_ticks"] == 2
        assert status["last_tick"] is not None

    async def test_run_forever_exception_caught(self, strategy, executor):
        """Line 215-216: run_forever catches generic Exception from provider."""
        engine = TradingEngine(
            strategy=strategy,
            executor=executor,
            config=TradingEngineConfig(strategy_name="test", loop_interval=0.01),
        )
        strategy.analyze.return_value = None

        class FailingProvider:
            call_count = 0

            async def __call__(self):
                self.call_count += 1
                if self.call_count == 1:
                    return MarketSnapshot(
                        market_id="mkt1",
                        timestamp=datetime(2026, 7, 4),
                        bid_price=0.5,
                        ask_price=0.6,
                        mid_price=0.55,
                        bid_size=100.0,
                        ask_size=100.0,
                    )
                raise ValueError("provider error")

        provider = FailingProvider()
        loop_task = asyncio.create_task(engine.run_forever(provider))
        await asyncio.sleep(0.05)
        await engine.stop()
        await loop_task
        # Exception was caught, engine stopped cleanly
        assert engine._running is False

    async def test_risk_gate_approved_line_174(self, strategy, executor, market):
        """Execute result dict with 'status' key not matching any known status."""
        risk = AsyncMock(spec=RiskGate)
        risk.evaluate = AsyncMock(
            return_value=RiskDecision(
                gate_name="tg",
                approved=True,
                reason="ok",
            )
        )
        engine = TradingEngine(strategy=strategy, executor=executor, risk_manager=risk)
        order = OrderIntent(market_id="mkt1", side=OrderSide.BUY, price=0.45, size=10.0)
        strategy.analyze.return_value = StrategyIntent(
            timestamp=datetime(2026, 7, 4, 12, 0, 0),
            strategy_name="test",
            orders=[order],
        )
        executor.execute.return_value = {}
        result = await engine.run_tick(market)
        assert result.risk_approved is True

    async def test_run_tick_all_filter(self, executor: AsyncMock, market: MarketSnapshot):
        """run_tick_all filters markets via strategy.filter_markets."""
        from datetime import datetime, timezone

        from polymind.core.strategy import BaseMMStrategy, StrategyConfig, StrategyIntent

        class FilterTestStrategy(BaseMMStrategy):
            def __init__(self):
                super().__init__(config=StrategyConfig(name="filter_test"))

            def filter_markets(self, markets):
                return [m for m in markets if getattr(m, "market_id", "") == "mkt_ok"]

            async def analyze(self, market):
                return StrategyIntent(
                    timestamp=datetime.now(timezone.utc),
                    strategy_name=self.name,
                    orders=[],
                )

        strategy = FilterTestStrategy()
        engine = TradingEngine(strategy=strategy, executor=executor)

        mkt1 = MarketSnapshot(
            market_id="mkt_no",
            timestamp=datetime(2026, 7, 4),
            bid_price=0.5,
            ask_price=0.6,
            mid_price=0.55,
            bid_size=100,
            ask_size=100,
        )
        mkt2 = MarketSnapshot(
            market_id="mkt_ok",
            timestamp=datetime(2026, 7, 4),
            bid_price=0.5,
            ask_price=0.6,
            mid_price=0.55,
            bid_size=100,
            ask_size=100,
        )

        results = await engine.run_tick_all([mkt1, mkt2])
        assert len(results) == 1
        assert results[0].strategy == "filter_test"
