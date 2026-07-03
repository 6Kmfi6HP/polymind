"""
Tests for PaperExecutor.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import (
    CancelIntent,
    IntentExecutor,
    OrderIntent,
    OrderSide,
    StrategyIntent,
)
from polymind.core.ledger import EntryType, LedgerEntry
from polymind.execution.executor import OrderRecord, OrderStatus, PaperExecutor, PositionRecord
from polymind.execution.fill_model import FillMode, FillModel, FillModelConfig, MarketSnapshot
from polymind.execution.order_identity import OrderIdentity


@pytest.fixture
def snap() -> MarketSnapshot:
    return MarketSnapshot(
        market_id="0xabc",
        bid_price=0.80,
        bid_size=100.0,
        ask_price=0.85,
        ask_size=200.0,
        mid_price=0.825,
        timestamp=datetime.now(),
    )


@pytest.fixture
def taker_executor() -> PaperExecutor:
    """A PaperExecutor configured with taker fill model for deterministic fills."""
    cfg = FillModelConfig(mode=FillMode.TAKER, taker_fee_rate=0.003)
    model = FillModel(cfg)
    return PaperExecutor(fill_model=model, initial_cash=10_000.0)


class TestPaperExecutorInit:
    def test_default_initialization(self):
        cfg = FillModelConfig(mode=FillMode.PASSIVE)
        model = FillModel(cfg)
        ex = PaperExecutor(fill_model=model)
        assert ex.initial_cash == 10_000.0
        assert ex.cash == 10_000.0
        assert ex.orders == {}
        assert ex.fills == []
        assert ex.ledger == []
        assert ex.positions == {}
        assert ex.loop_interval == 60

    def test_custom_initialization(self):
        cfg = FillModelConfig(mode=FillMode.PASSIVE)
        model = FillModel(cfg)
        ex = PaperExecutor(fill_model=model, initial_cash=5_000.0, loop_interval=30)
        assert ex.initial_cash == 5_000.0
        assert ex.cash == 5_000.0
        assert ex.loop_interval == 30

    def test_is_intent_executor(self):
        cfg = FillModelConfig(mode=FillMode.PASSIVE)
        model = FillModel(cfg)
        ex = PaperExecutor(fill_model=model)
        assert isinstance(ex, IntentExecutor)


class TestPaperExecutorExecute:
    @pytest.mark.asyncio
    async def test_place_order(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """Executing a StrategyIntent with one OrderIntent should create an order."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        taker_executor._current_snapshot = snap
        result = await taker_executor.execute(intent)
        assert len(taker_executor.orders) == 1
        assert result["0xabc"]["orders_placed"] == 1

    @pytest.mark.asyncio
    async def test_immediate_fill_on_execute(
        self, taker_executor: PaperExecutor, snap: MarketSnapshot
    ):
        """TAKER mode should fill orders immediately during execute()."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        taker_executor._current_snapshot = snap
        result = await taker_executor.execute(intent)
        assert result["0xabc"]["fills"] == 1
        assert result["0xabc"]["filled_size"] == 10.0

    @pytest.mark.asyncio
    async def test_execute_dedupe(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """Same OrderIntent should not create duplicate orders."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        taker_executor._current_snapshot = snap
        await taker_executor.execute(intent)
        await taker_executor.execute(intent)  # same intent again
        assert len(taker_executor.orders) == 1

    @pytest.mark.asyncio
    async def test_cancel_order(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """CancelIntent should mark an open order as CANCELLED."""
        buy_intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.75,  # won't cross ask=0.85 in passive mode
                    size=10.0,
                ),
            ],
        )
        cfg = FillModelConfig(mode=FillMode.PASSIVE)
        model = FillModel(cfg)
        ex = PaperExecutor(fill_model=model, initial_cash=10_000.0)
        ex._current_snapshot = snap
        await ex.execute(buy_intent)

        oid = list(ex.orders.keys())[0]
        cancel_intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            cancels=[
                CancelIntent(market_id="0xabc", order_id=oid, reason="price shift"),
            ],
        )
        result = await ex.execute(cancel_intent)
        assert ex.orders[oid].status == OrderStatus.CANCELLED
        assert result["0xabc"]["cancelled"] == 1

    @pytest.mark.asyncio
    async def test_cancel_all(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """CancelIntent with no order_id should cancel all orders for that market."""
        # Place 2 orders with different prices
        ex = taker_executor
        ex._current_snapshot = snap
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(market_id="0xabc", side=OrderSide.BUY, price=0.75, size=5.0),
            ],
        )
        # Need passive mode so orders stay open
        cfg = FillModelConfig(mode=FillMode.PASSIVE)
        model = FillModel(cfg)
        ex2 = PaperExecutor(fill_model=model, initial_cash=10_000.0)
        ex2._current_snapshot = snap
        await ex2.execute(intent)

        # Cancel all
        cancel_intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            cancels=[CancelIntent(market_id="0xabc", reason="reset")],
        )
        result = await ex2.execute(cancel_intent)
        assert result["0xabc"]["cancelled"] > 0

    @pytest.mark.asyncio
    async def test_dry_run(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """dry_run() should not place any orders."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        result = await taker_executor.dry_run(intent)
        assert result["dry_run"] is True
        assert result["orders_proposed"] == 1
        assert len(taker_executor.orders) == 0  # no orders placed


class TestPaperExecutorFillRecording:
    @pytest.mark.asyncio
    async def test_fill_event_recorded(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """Fills should be recorded as FillEvents."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        taker_executor._current_snapshot = snap
        await taker_executor.execute(intent)
        assert len(taker_executor.fills) == 1
        assert isinstance(taker_executor.fills[0], FillEvent)
        assert taker_executor.fills[0].market_id == "0xabc"
        assert taker_executor.fills[0].source == FillSource.SIMULATED

    @pytest.mark.asyncio
    async def test_ledger_entry_recorded(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """Fills should produce LedgerEntries."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        taker_executor._current_snapshot = snap
        await taker_executor.execute(intent)
        assert len(taker_executor.ledger) > 0
        assert isinstance(taker_executor.ledger[0], LedgerEntry)

    @pytest.mark.asyncio
    async def test_cash_balance_updates(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """Cash should decrease after a buy fill."""
        initial = taker_executor.cash
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        taker_executor._current_snapshot = snap
        await taker_executor.execute(intent)
        assert taker_executor.cash < initial

    @pytest.mark.asyncio
    async def test_sell_increases_cash(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """Sell should increase cash."""
        # Buy first
        buy_intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        taker_executor._current_snapshot = snap
        await taker_executor.execute(buy_intent)
        cash_after_buy = taker_executor.cash

        # Sell
        sell_intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.SELL,
                    price=0.80,
                    size=10.0,
                ),
            ],
        )
        # Snapshot with different price for sell simulation
        sell_snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        taker_executor._current_snapshot = sell_snap
        await taker_executor.execute(sell_intent)
        assert taker_executor.cash > cash_after_buy


class TestPaperExecutorSimulateTick:
    @pytest.mark.asyncio
    async def test_simulate_tick_no_fills(self):
        """Tick should return 0 fills when no orders are open."""
        cfg = FillModelConfig(mode=FillMode.PASSIVE)
        model = FillModel(cfg)
        ex = PaperExecutor(fill_model=model)
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        fills = await ex.simulate_tick(snap)
        assert fills == 0

    @pytest.mark.asyncio
    async def test_simulate_tick_with_fills(self):
        """Tick should fill orders that cross the spread after a price move."""
        cfg = FillModelConfig(mode=FillMode.PASSIVE)
        model = FillModel(cfg)
        ex = PaperExecutor(fill_model=model)

        # Place a buy order at 0.84 (below ask 0.85 — NOT crossing initially)
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.84,
                    size=10.0,
                ),
            ],
        )
        ex._current_snapshot = snap
        await ex.execute(intent)

        # Now the order is open (not crossing). Simulate a tick with
        # a new snapshot where ask drops to 0.83 — order should fill.
        new_snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.78,
            bid_size=100.0,
            ask_price=0.83,
            ask_size=200.0,
            mid_price=0.805,
            timestamp=datetime.now(),
        )
        fills = await ex.simulate_tick(new_snap)
        assert fills > 0


class TestPaperExecutorPositionAndStatus:
    @pytest.mark.asyncio
    async def test_get_position(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """get_position() should return current position."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        taker_executor._current_snapshot = snap
        await taker_executor.execute(intent)
        pos = taker_executor.get_position("0xabc")
        assert pos is not None
        assert pos.market_id == "0xabc"
        assert pos.size == 10.0

    @pytest.mark.asyncio
    async def test_get_position_missing(self, taker_executor: PaperExecutor):
        """get_position() should return None for unknown market."""
        pos = taker_executor.get_position("0xnonexistent")
        assert pos is None

    @pytest.mark.asyncio
    async def test_get_open_order_count(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """get_open_order_count() should return correct count."""
        # Taker fills immediately so no open orders
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        taker_executor._current_snapshot = snap
        await taker_executor.execute(intent)
        # All filled immediately, so open count should be 0
        assert taker_executor.get_open_order_count() == 0

    @pytest.mark.asyncio
    async def test_open_order_count_passive(self):
        """Passive orders should remain open until tick crosses price."""
        cfg = FillModelConfig(mode=FillMode.PASSIVE)
        model = FillModel(cfg)
        ex = PaperExecutor(fill_model=model)
        snap = MarketSnapshot(
            market_id="0xabc",
            bid_price=0.80,
            bid_size=100.0,
            ask_price=0.85,
            ask_size=200.0,
            mid_price=0.825,
            timestamp=datetime.now(),
        )
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.75,  # below bid, won't cross
                    size=10.0,
                ),
            ],
        )
        ex._current_snapshot = snap
        await ex.execute(intent)
        assert ex.get_open_order_count() == 1


class TestPaperExecutorShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self, taker_executor: PaperExecutor, snap: MarketSnapshot):
        """shutdown() should clear all state."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        taker_executor._current_snapshot = snap
        await taker_executor.execute(intent)
        await taker_executor.shutdown()
        assert len(taker_executor.orders) == 0
        assert len(taker_executor.fills) == 0
        assert len(taker_executor.ledger) == 0


class TestOrderRecord:
    def test_minimal_construction(self):
        now = datetime.now(timezone.utc)
        oid = OrderIdentity(
            strategy_name="test",
            market_id="0xabc",
            side=OrderSide.BUY,
            price=0.85,
            outcome="YES",
            client_id="c1",
        )
        intent = OrderIntent(market_id="0xabc", side=OrderSide.BUY, price=0.85, size=10.0)
        rec = OrderRecord(
            identity=oid,
            intent=intent,
            status=OrderStatus.OPEN,
            created_at=now,
        )
        assert rec.identity == oid
        assert rec.intent == intent
        assert rec.status == OrderStatus.OPEN
        assert rec.filled_size == 0.0


class TestPositionRecord:
    def test_construction(self):
        pos = PositionRecord(
            market_id="0xabc",
            outcome="YES",
            size=10.0,
            avg_entry=0.85,
            realized_pnl=0.0,
        )
        assert pos.market_id == "0xabc"
        assert pos.size == 10.0
        assert pos.avg_entry == 0.85
        assert pos.realized_pnl == 0.0
