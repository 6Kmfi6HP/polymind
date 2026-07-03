"""
Tests for the Intent / Executor domain layer (ADR 0002).
"""

from datetime import datetime, timezone
from typing import Any

from polymind.core.intents import (
    CancelIntent,
    IntentExecutor,
    OrderIntent,
    OrderSide,
    StrategyIntent,
    TimeInForce,
)


class TestOrderIntent:
    """OrderIntent is a plain dataclass — test construction and defaults."""

    def test_minimal_construction(self):
        intent = OrderIntent(market_id="0xabc", side=OrderSide.BUY, price=0.85, size=10.0)
        assert intent.market_id == "0xabc"
        assert intent.side == OrderSide.BUY
        assert intent.price == 0.85
        assert intent.size == 10.0
        assert intent.outcome is None
        assert intent.time_in_force == TimeInForce.GTC
        assert intent.reduce_only is False

    def test_full_construction(self):
        expiry = datetime(2026, 7, 4, tzinfo=timezone.utc)
        intent = OrderIntent(
            market_id="0xdef",
            side=OrderSide.SELL,
            price=0.92,
            size=5.0,
            outcome="YES",
            time_in_force=TimeInForce.IOC,
            expiration=expiry,
            reduce_only=True,
            metadata={"reason": "stop-loss"},
        )
        assert intent.side == OrderSide.SELL
        assert intent.outcome == "YES"
        assert intent.time_in_force == TimeInForce.IOC
        assert intent.expiration == expiry
        assert intent.reduce_only is True
        assert intent.metadata["reason"] == "stop-loss"


class TestCancelIntent:
    def test_cancel_specific_order(self):
        intent = CancelIntent(market_id="0xabc", order_id="ord-123", reason="price moved")
        assert intent.market_id == "0xabc"
        assert intent.order_id == "ord-123"
        assert intent.reason == "price moved"

    def test_cancel_all_for_market(self):
        intent = CancelIntent(market_id="0xabc")
        assert intent.order_id is None  # None means cancel all


class TestStrategyIntent:
    def test_empty_by_default(self):
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(timestamp=now, strategy_name="test")
        assert intent.is_empty()
        assert len(intent.orders) == 0
        assert len(intent.cancels) == 0

    def test_not_empty_with_orders(self):
        now = datetime.now(timezone.utc)
        order = OrderIntent(market_id="0x1", side=OrderSide.BUY, price=0.5, size=1.0)
        intent = StrategyIntent(timestamp=now, strategy_name="test", orders=[order])
        assert not intent.is_empty()

    def test_not_empty_with_cancels(self):
        now = datetime.now(timezone.utc)
        cancel = CancelIntent(market_id="0x1")
        intent = StrategyIntent(timestamp=now, strategy_name="test", cancels=[cancel])
        assert not intent.is_empty()

    def test_risk_override_optional(self):
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(
            timestamp=now,
            strategy_name="test",
            risk_override={"max_position_size": 100.0},
        )
        assert intent.risk_override == {"max_position_size": 100.0}

    def test_metadata_roundtrip(self):
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(
            timestamp=now,
            strategy_name="test",
            metadata={"version": 2, "tags": ["live"]},
        )
        assert intent.metadata["version"] == 2


class TestIntentExecutor:
    """Test the abstract executor protocol."""

    async def test_dry_run_logs_and_returns(self):
        class DummyExecutor(IntentExecutor):
            async def execute(self, intent: StrategyIntent) -> dict[str, Any]:
                return {"status": "executed"}

        executor = DummyExecutor()
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(timestamp=now, strategy_name="test")

        result = await executor.dry_run(intent)
        assert result["dry_run"] is True
        assert result["orders_proposed"] == 0

        await executor.shutdown()

    async def test_execute_abstract(self):
        """Subclass must implement execute()."""
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(timestamp=now, strategy_name="test")

        executor = ConcreteTestExecutor()
        result = await executor.execute(intent)
        assert result["status"] == "ok"


class ConcreteTestExecutor(IntentExecutor):
    """Concrete subclass for testing the abstract protocol."""

    async def execute(self, intent: StrategyIntent) -> dict[str, Any]:
        return {
            "status": "ok",
            "strategy": intent.strategy_name,
            "order_count": len(intent.orders),
        }
