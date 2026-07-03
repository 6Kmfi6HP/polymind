"""
Tests for RecoveryManager and related domain types.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import OrderSide
from polymind.reconciliation.fills import (
    FillReconciliationRecord,
    ReconciliationStatus,
)
from polymind.reconciliation.recovery import (
    RecoveryAction,
    RecoveryManager,
    RecoveryRecord,
)


class TestRecoveryAction:
    def test_all_values_defined(self):
        expected = {"IGNORE", "RETRY_ORDER", "CANCEL_REPLACE", "CLOSE_POSITION", "ESCALATE"}
        assert {e.name for e in RecoveryAction} == expected

    def test_values_are_distinct(self):
        values = list(RecoveryAction)
        assert len(values) == len(set(values))


class TestRecoveryRecord:
    def test_minimal_construction(self):
        now = datetime.now()
        record = RecoveryRecord(
            fill_id="fill-001",
            market_id="0xabc",
            issue="Fill missing",
            action=RecoveryAction.RETRY_ORDER,
            resolved=False,
            timestamp=now,
        )
        assert record.fill_id == "fill-001"
        assert record.market_id == "0xabc"
        assert record.issue == "Fill missing"
        assert record.action == RecoveryAction.RETRY_ORDER
        assert record.resolved is False
        assert record.timestamp == now
        assert record.metadata == {}

    def test_with_metadata(self):
        now = datetime.now()
        record = RecoveryRecord(
            fill_id="fill-002",
            market_id="0xdef",
            issue="Escalated",
            action=RecoveryAction.ESCALATE,
            resolved=False,
            timestamp=now,
            metadata={"reason": "max retries exceeded"},
        )
        assert record.metadata["reason"] == "max retries exceeded"

    def test_resolved_record(self):
        now = datetime.now()
        record = RecoveryRecord(
            fill_id="fill-003",
            market_id="0xabc",
            issue="OK",
            action=RecoveryAction.IGNORE,
            resolved=True,
            timestamp=now,
        )
        assert record.resolved is True


class TestRecoveryManagerInit:
    def test_default_max_retries(self):
        manager = RecoveryManager()
        assert manager._max_retries == 3

    def test_custom_max_retries(self):
        manager = RecoveryManager(max_retries=5)
        assert manager._max_retries == 5

    def test_initial_state_empty(self):
        manager = RecoveryManager()
        assert manager._retry_counts == {}
        assert manager._history == []


class TestAssess:
    @pytest.mark.asyncio
    async def test_assess_matched_returns_ignore(self):
        fill = _make_fill("f1")
        record = _make_record("f1", ReconciliationStatus.MATCHED)
        manager = RecoveryManager()

        action = await manager.assess(fill, record)

        assert action == RecoveryAction.IGNORE

    @pytest.mark.asyncio
    async def test_assess_missing_returns_retry_order(self):
        fill = _make_fill("f2")
        record = _make_record("f2", ReconciliationStatus.MISSING)
        manager = RecoveryManager()

        action = await manager.assess(fill, record)

        assert action == RecoveryAction.RETRY_ORDER

    @pytest.mark.asyncio
    async def test_assess_mismatched_returns_cancel_replace(self):
        fill = _make_fill("f3")
        record = _make_record("f3", ReconciliationStatus.MISMATCHED)
        manager = RecoveryManager()

        action = await manager.assess(fill, record)

        assert action == RecoveryAction.CANCEL_REPLACE

    @pytest.mark.asyncio
    async def test_assess_unexpected_returns_ignore(self):
        fill = _make_fill("f4")
        record = _make_record("f4", ReconciliationStatus.UNEXPECTED)
        manager = RecoveryManager()

        action = await manager.assess(fill, record)

        assert action == RecoveryAction.IGNORE

    @pytest.mark.asyncio
    async def test_assess_escalate_after_max_retries(self):
        fill = _make_fill("f5")
        record = _make_record("f5", ReconciliationStatus.MISSING)
        manager = RecoveryManager(max_retries=2)

        # First two calls should return RETRY_ORDER
        action1 = await manager.assess(fill, record)
        assert action1 == RecoveryAction.RETRY_ORDER
        await manager.execute(RecoveryAction.RETRY_ORDER, fill)

        action2 = await manager.assess(fill, record)
        assert action2 == RecoveryAction.RETRY_ORDER
        await manager.execute(RecoveryAction.RETRY_ORDER, fill)

        # Third call should escalate (2 retries exhausted)
        action3 = await manager.assess(fill, record)
        assert action3 == RecoveryAction.ESCALATE

    @pytest.mark.asyncio
    async def test_assess_respects_max_retries_per_fill(self):
        fill_a = _make_fill("fA")
        fill_b = _make_fill("fB")
        record_a = _make_record("fA", ReconciliationStatus.MISSING)
        record_b = _make_record("fB", ReconciliationStatus.MISSING)
        manager = RecoveryManager(max_retries=1)

        # Retry fill_a once
        await manager.execute(RecoveryAction.RETRY_ORDER, fill_a)
        # fill_a now exceeds retries
        assert await manager.assess(fill_a, record_a) == RecoveryAction.ESCALATE
        # fill_b still has 0 retries
        assert await manager.assess(fill_b, record_b) == RecoveryAction.RETRY_ORDER


class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_ignore(self):
        fill = _make_fill("f1")
        manager = RecoveryManager()

        resolved = await manager.execute(RecoveryAction.IGNORE, fill)

        assert resolved is True
        assert len(manager._history) == 1
        assert manager._history[0].action == RecoveryAction.IGNORE
        assert manager._history[0].resolved is True

    @pytest.mark.asyncio
    async def test_execute_retry_order(self):
        fill = _make_fill("f2")
        manager = RecoveryManager()

        resolved = await manager.execute(RecoveryAction.RETRY_ORDER, fill)

        assert resolved is False
        assert manager._retry_counts["f2"] == 1
        assert len(manager._history) == 1
        assert manager._history[0].action == RecoveryAction.RETRY_ORDER

    @pytest.mark.asyncio
    async def test_execute_cancel_replace(self):
        fill = _make_fill("f3")
        manager = RecoveryManager()

        resolved = await manager.execute(RecoveryAction.CANCEL_REPLACE, fill)

        assert resolved is False
        assert manager._retry_counts["f3"] == 1
        assert manager._history[0].action == RecoveryAction.CANCEL_REPLACE

    @pytest.mark.asyncio
    async def test_execute_close_position(self):
        fill = _make_fill("f4")
        manager = RecoveryManager()

        resolved = await manager.execute(RecoveryAction.CLOSE_POSITION, fill)

        assert resolved is False
        assert manager._history[0].action == RecoveryAction.CLOSE_POSITION

    @pytest.mark.asyncio
    async def test_execute_escalate(self):
        fill = _make_fill("f5")
        manager = RecoveryManager()

        resolved = await manager.execute(RecoveryAction.ESCALATE, fill)

        assert resolved is False
        assert "escalation" in manager._history[0].issue.lower()

    @pytest.mark.asyncio
    async def test_execute_increments_retry_count_only_for_retry_actions(self):
        fill = _make_fill("f6")
        manager = RecoveryManager()

        await manager.execute(RecoveryAction.IGNORE, fill)
        assert "f6" not in manager._retry_counts

        await manager.execute(RecoveryAction.RETRY_ORDER, fill)
        assert manager._retry_counts["f6"] == 1

        await manager.execute(RecoveryAction.CANCEL_REPLACE, fill)
        assert manager._retry_counts["f6"] == 2


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_get_history_returns_records_in_order(self):
        fill = _make_fill("f1")
        manager = RecoveryManager()

        await manager.execute(RecoveryAction.RETRY_ORDER, fill)
        await manager.execute(RecoveryAction.IGNORE, fill)

        history = manager.get_history()
        assert len(history) == 2
        assert history[0].action == RecoveryAction.RETRY_ORDER
        assert history[1].action == RecoveryAction.IGNORE

    @pytest.mark.asyncio
    async def test_get_history_returns_copy(self):
        fill = _make_fill("f1")
        manager = RecoveryManager()

        await manager.execute(RecoveryAction.IGNORE, fill)
        history = manager.get_history()
        history.clear()
        # Original should be unaffected
        assert len(manager._history) == 1

    def test_get_history_empty_on_new_manager(self):
        manager = RecoveryManager()
        assert manager.get_history() == []


class TestClose:
    @pytest.mark.asyncio
    async def test_close_clears_state(self):
        fill = _make_fill("f1")
        manager = RecoveryManager()

        await manager.execute(RecoveryAction.RETRY_ORDER, fill)
        assert len(manager._history) == 1
        assert manager._retry_counts["f1"] == 1

        await manager.close()
        assert manager._history == []
        assert manager._retry_counts == {}

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        manager = RecoveryManager()

        await manager.close()
        await manager.close()
        # Should not raise
        assert manager._history == []
        assert manager._retry_counts == {}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_fill(fill_id: str) -> FillEvent:
    return FillEvent(
        fill_id=fill_id,
        market_id="0xabc",
        outcome="YES",
        side=OrderSide.BUY,
        price=0.85,
        size=10.0,
        fee=0.01,
        timestamp=datetime.now(),
        source=FillSource.SIMULATED,
    )


def _make_record(fill_id: str, status: ReconciliationStatus) -> FillReconciliationRecord:
    return FillReconciliationRecord(
        market_id="0xabc",
        identity_string=fill_id,
        expected_fill_size=10.0,
        expected_fill_price=0.85,
        actual_fill_size=10.0,
        actual_fill_price=0.85,
        status=status,
        discrepancy=0.0,
        timestamp=datetime.now(),
    )
