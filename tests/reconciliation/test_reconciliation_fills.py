"""
Tests for FillReconciler and related domain types.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import OrderSide
from polymind.polymarket.client import PolymarketClient
from polymind.polymarket.websocket import PolymarketWebSocketAdapter
from polymind.reconciliation.fills import (
    FillReconciler,
    FillReconciliationRecord,
    ReconciliationStatus,
)


class TestReconciliationStatus:
    def test_enum_values(self):
        assert ReconciliationStatus.MATCHED != ReconciliationStatus.MISMATCHED
        assert ReconciliationStatus.MISSING != ReconciliationStatus.UNEXPECTED

    def test_all_statuses_defined(self):
        expected = {"MATCHED", "MISMATCHED", "MISSING", "UNEXPECTED"}
        assert {e.name for e in ReconciliationStatus} == expected


class TestFillReconciliationRecord:
    def test_minimal_construction(self):
        now = datetime.now()
        record = FillReconciliationRecord(
            market_id="0xabc",
            identity_string="identity-1",
            expected_fill_size=10.0,
            expected_fill_price=0.85,
            actual_fill_size=10.0,
            actual_fill_price=0.85,
            status=ReconciliationStatus.MATCHED,
            discrepancy=0.0,
            timestamp=now,
        )
        assert record.market_id == "0xabc"
        assert record.identity_string == "identity-1"
        assert record.expected_fill_size == 10.0
        assert record.expected_fill_price == 0.85
        assert record.actual_fill_size == 10.0
        assert record.actual_fill_price == 0.85
        assert record.status == ReconciliationStatus.MATCHED
        assert record.discrepancy == 0.0
        assert record.timestamp == now
        assert record.metadata == {}

    def test_with_metadata(self):
        now = datetime.now()
        record = FillReconciliationRecord(
            market_id="0xdef",
            identity_string="identity-2",
            expected_fill_size=5.0,
            expected_fill_price=0.50,
            actual_fill_size=4.0,
            actual_fill_price=0.51,
            status=ReconciliationStatus.MISMATCHED,
            discrepancy=1.0,
            timestamp=now,
            metadata={"notes": "slippage detected"},
        )
        assert record.metadata["notes"] == "slippage detected"

    def test_missing_record(self):
        now = datetime.now()
        record = FillReconciliationRecord(
            market_id="0xabc",
            identity_string="identity-3",
            expected_fill_size=10.0,
            expected_fill_price=0.85,
            actual_fill_size=0.0,
            actual_fill_price=0.0,
            status=ReconciliationStatus.MISSING,
            discrepancy=10.0,
            timestamp=now,
        )
        assert record.status == ReconciliationStatus.MISSING
        assert record.actual_fill_size == 0.0
        assert record.discrepancy == 10.0


class TestFillReconcilerInit:
    def test_init_with_none(self):
        reconciler = FillReconciler()
        assert reconciler._websocket_adapter is None
        assert reconciler._clob_client is None

    def test_init_with_mock_clients(self):
        ws = MagicMock(spec=PolymarketWebSocketAdapter)
        clob = MagicMock(spec=PolymarketClient)
        reconciler = FillReconciler(
            websocket_adapter=ws,
            clob_client=clob,
        )
        assert reconciler._websocket_adapter is ws
        assert reconciler._clob_client is clob


class TestFillReconcilerReconcileSingle:
    @pytest.mark.asyncio
    async def test_reconcile_single_matched(self):
        """A fill present in actual data with matching size/price should be MATCHED."""
        now = datetime.now()
        expected = FillEvent(
            fill_id="fill-001",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.SIMULATED,
            order_id="ord-001",
        )
        actual = FillEvent(
            fill_id="fill-001",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.CLOB_API,
            order_id="ord-001",
        )

        clob = AsyncMock(spec=PolymarketClient)
        clob.get_fills = AsyncMock(return_value=[actual])
        reconciler = FillReconciler(clob_client=clob)

        record = await reconciler.reconcile_single(expected)
        assert record.status == ReconciliationStatus.MATCHED
        assert record.discrepancy == 0.0
        assert record.expected_fill_size == 10.0
        assert record.actual_fill_size == 10.0

    @pytest.mark.asyncio
    async def test_reconcile_single_mismatch_size(self):
        """When actual size differs from expected, status should be MISMATCHED."""
        now = datetime.now()
        expected = FillEvent(
            fill_id="fill-002",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.SIMULATED,
            order_id="ord-002",
        )
        actual = FillEvent(
            fill_id="fill-002",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=9.5,
            fee=0.0095,
            timestamp=now,
            source=FillSource.CLOB_API,
            order_id="ord-002",
        )

        clob = AsyncMock(spec=PolymarketClient)
        clob.get_fills = AsyncMock(return_value=[actual])
        reconciler = FillReconciler(clob_client=clob)

        record = await reconciler.reconcile_single(expected)
        assert record.status == ReconciliationStatus.MISMATCHED
        assert record.discrepancy == 0.5
        assert record.expected_fill_size == 10.0
        assert record.actual_fill_size == 9.5

    @pytest.mark.asyncio
    async def test_reconcile_single_missing(self):
        """When no actual fill matches, status should be MISSING."""
        now = datetime.now()
        expected = FillEvent(
            fill_id="fill-003",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.SIMULATED,
            order_id="ord-003",
        )

        clob = AsyncMock(spec=PolymarketClient)
        clob.get_fills = AsyncMock(return_value=[])
        reconciler = FillReconciler(clob_client=clob)

        record = await reconciler.reconcile_single(expected)
        assert record.status == ReconciliationStatus.MISSING
        assert record.discrepancy == 10.0
        assert record.actual_fill_size == 0.0


class TestFillReconcilerReconcileFills:
    @pytest.mark.asyncio
    async def test_reconcile_fills_produces_records(self):
        """reconcile_fills should produce a record for each expected fill."""
        now = datetime.now()
        expected_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.SIMULATED,
            ),
            FillEvent(
                fill_id="fill-002",
                market_id="0xabc",
                outcome="NO",
                side=OrderSide.SELL,
                price=0.15,
                size=5.0,
                fee=0.005,
                timestamp=now,
                source=FillSource.SIMULATED,
            ),
        ]
        actual_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.CLOB_API,
            ),
        ]

        clob = AsyncMock(spec=PolymarketClient)
        clob.get_fills = AsyncMock(return_value=actual_fills)
        reconciler = FillReconciler(clob_client=clob)

        records = await reconciler.reconcile_fills(expected_fills, market_id="0xabc")
        assert len(records) == 2
        # fill-001 should be MATCHED
        matched = [r for r in records if r.status == ReconciliationStatus.MATCHED]
        assert len(matched) == 1
        # fill-002 should be MISSING (not in actual data)
        missing = [r for r in records if r.status == ReconciliationStatus.MISSING]
        assert len(missing) == 1

    @pytest.mark.asyncio
    async def test_reconcile_fills_detects_unexpected(self):
        """Actual fills with no matching expected fill should be UNEXPECTED."""
        now = datetime.now()
        expected_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.SIMULATED,
            ),
        ]
        actual_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.CLOB_API,
            ),
            FillEvent(
                fill_id="fill-999",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.86,
                size=3.0,
                fee=0.003,
                timestamp=now,
                source=FillSource.CLOB_API,
            ),
        ]

        clob = AsyncMock(spec=PolymarketClient)
        clob.get_fills = AsyncMock(return_value=actual_fills)
        reconciler = FillReconciler(clob_client=clob)

        records = await reconciler.reconcile_fills(expected_fills, market_id="0xabc")
        assert len(records) == 2
        unexpected = [r for r in records if r.status == ReconciliationStatus.UNEXPECTED]
        assert len(unexpected) == 1
        assert unexpected[0].actual_fill_size == 3.0
        assert unexpected[0].expected_fill_size == 0.0


class TestFillReconcilerCrossCheck:
    def test_cross_check_matched(self):
        """Fills present in both sources with matching data should be MATCHED."""
        now = datetime.now()
        ws_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.WEBSOCKET,
            ),
        ]
        clob_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.CLOB_API,
            ),
        ]

        reconciler = FillReconciler()
        records = reconciler.cross_check_fills(ws_fills, clob_fills)
        matched = [r for r in records if r.status == ReconciliationStatus.MATCHED]
        assert len(matched) == 1
        assert matched[0].discrepancy == 0.0

    def test_cross_check_mismatched(self):
        """Fills present in both sources but with different sizes should be MISMATCHED."""
        now = datetime.now()
        ws_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.WEBSOCKET,
            ),
        ]
        clob_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=9.5,
                fee=0.0095,
                timestamp=now,
                source=FillSource.CLOB_API,
            ),
        ]

        reconciler = FillReconciler()
        records = reconciler.cross_check_fills(ws_fills, clob_fills)
        mismatched = [r for r in records if r.status == ReconciliationStatus.MISMATCHED]
        assert len(mismatched) == 1
        assert mismatched[0].discrepancy == 0.5

    def test_cross_check_unexpected_from_clob(self):
        """CLOB fills with no WebSocket counterpart should be UNEXPECTED."""
        now = datetime.now()
        ws_fills: list[FillEvent] = []
        clob_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.CLOB_API,
            ),
        ]

        reconciler = FillReconciler()
        records = reconciler.cross_check_fills(ws_fills, clob_fills)
        unexpected = [r for r in records if r.status == ReconciliationStatus.UNEXPECTED]
        # CLOB fill with no WS counterpart becomes UNEXPECTED
        assert len(unexpected) == 1

    def test_cross_check_unexpected_from_websocket(self):
        """WebSocket fills with no CLOB counterpart should be UNEXPECTED."""
        now = datetime.now()
        ws_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=10.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.WEBSOCKET,
            ),
        ]
        clob_fills: list[FillEvent] = []

        reconciler = FillReconciler()
        records = reconciler.cross_check_fills(ws_fills, clob_fills)
        unexpected = [r for r in records if r.status == ReconciliationStatus.UNEXPECTED]
        assert len(unexpected) == 1


class TestFillReconcilerClose:
    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        """close() should be safe to call multiple times."""
        ws = AsyncMock(spec=PolymarketWebSocketAdapter)
        ws.close = AsyncMock()
        reconciler = FillReconciler(websocket_adapter=ws)

        await reconciler.close()
        ws.close.assert_called_once()

        # Second call should also succeed (idempotent)
        await reconciler.close()
        assert ws.close.call_count == 2

    @pytest.mark.asyncio
    async def test_close_with_no_websocket(self):
        """close() should not error when no websocket adapter was provided."""
        reconciler = FillReconciler()
        # Should not raise
        await reconciler.close()
