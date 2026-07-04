"""
Integration: TradingEngine + RiskGate.

Verifies that risk gates wired into TradingEngine correctly
reject oversized intents and pass compliant ones.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.engine import TradingEngine
from polymind.core.intents import OrderIntent, OrderSide, StrategyIntent
from polymind.core.risk import RiskContext, RiskDecision, RiskGate
from polymind.execution.executor import PaperExecutor
from polymind.execution.fill_model import FillMode, FillModel, FillModelConfig, MarketSnapshot


class MaxPositionGate(RiskGate):
    """Rejects intents where any order.size > max_size."""

    name = "MaxPositionGate"

    def __init__(self, max_size: float = 10.0):
        self.max_size = max_size

    async def evaluate(
        self,
        intent: StrategyIntent,
        context: RiskContext,
    ) -> RiskDecision:
        for order in intent.orders:
            if order.size > self.max_size:
                return RiskDecision(
                    gate_name=self.name,
                    approved=False,
                    reason=f"Order size {order.size} exceeds max {self.max_size}",
                )
        return RiskDecision(gate_name=self.name, approved=True, reason="ok")


class AlwaysPassStrategy:
    """Simple strategy that returns pre-built intents."""

    name = "test_strat"

    def __init__(self, orders: list | None = None):
        self._orders = orders or []

    async def analyze(self, market: MarketSnapshot) -> StrategyIntent:
        return StrategyIntent(
            timestamp=datetime.now(),
            strategy_name=self.name,
            orders=self._orders,
        )


@pytest.fixture
def executor() -> PaperExecutor:
    return PaperExecutor(fill_model=FillModel(FillModelConfig(mode=FillMode.TAKER)))


@pytest.fixture
def market() -> MarketSnapshot:
    return MarketSnapshot(
        market_id="mkt1",
        timestamp=datetime(2026, 7, 4, 12, 0, 0),
        bid_price=0.45,
        ask_price=0.55,
        mid_price=0.50,
        bid_size=10_000.0,
        ask_size=10_000.0,
    )


class TestRiskIntegration:
    async def test_risk_rejects_oversized_intent(
        self, executor: PaperExecutor, market: MarketSnapshot
    ):
        gate = MaxPositionGate(max_size=5.0)
        strategy = AlwaysPassStrategy(
            orders=[OrderIntent(market_id="mkt1", side=OrderSide.BUY, price=0.5, size=100.0)],
        )
        engine = TradingEngine(strategy=strategy, executor=executor, risk_manager=gate)

        result = await engine.run_tick(market)

        assert result.risk_approved is False
        assert "max" in result.error.lower()

    async def test_risk_passes_compliant_intent(
        self, executor: PaperExecutor, market: MarketSnapshot
    ):
        gate = MaxPositionGate(max_size=10.0)
        strategy = AlwaysPassStrategy(
            orders=[OrderIntent(market_id="mkt1", side=OrderSide.BUY, price=0.5, size=5.0)],
        )
        engine = TradingEngine(strategy=strategy, executor=executor, risk_manager=gate)

        result = await engine.run_tick(market)

        assert result.risk_approved is True
        assert result.error == ""
