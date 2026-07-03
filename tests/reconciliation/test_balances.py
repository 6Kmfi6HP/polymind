"""
Tests for BalanceReconciler and related domain types.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from polymind.polymarket.contracts import ContractsGateway
from polymind.reconciliation.balances import (
    BalanceReconciler,
    BalanceSnapshot,
    BalanceStatus,
)


TOLERANCE = 0.0001


class TestBalanceStatus:
    def test_enum_values(self):
        assert BalanceStatus.CONSISTENT != BalanceStatus.DISCREPANCY
        assert BalanceStatus.UNAVAILABLE != BalanceStatus.CONSISTENT

    def test_all_statuses_defined(self):
        expected = {"CONSISTENT", "DISCREPANCY", "UNAVAILABLE"}
        assert {e.name for e in BalanceStatus} == expected


class TestBalanceSnapshot:
    def test_minimal_construction(self):
        now = datetime.now()
        snapshot = BalanceSnapshot(
            token_id="0x123",
            owner="0xabc",
            onchain_balance=100.0,
            local_balance=100.0,
            discrepancy=0.0,
            timestamp=now,
        )
        assert snapshot.token_id == "0x123"
        assert snapshot.owner == "0xabc"
        assert snapshot.onchain_balance == 100.0
        assert snapshot.local_balance == 100.0
        assert snapshot.discrepancy == 0.0
        assert snapshot.timestamp == now

    def test_consistent_discrepancy_zero(self):
        snapshot = BalanceSnapshot(
            token_id="t1",
            owner="0xabc",
            onchain_balance=50.0,
            local_balance=50.0,
            discrepancy=0.0,
            timestamp=datetime.now(),
        )
        assert snapshot.discrepancy < TOLERANCE

    def test_discrepancy_nonzero(self):
        snapshot = BalanceSnapshot(
            token_id="t1",
            owner="0xabc",
            onchain_balance=50.0,
            local_balance=45.0,
            discrepancy=5.0,
            timestamp=datetime.now(),
        )
        assert snapshot.discrepancy == 5.0


class TestBalanceReconcilerInit:
    def test_init_with_none(self):
        reconciler = BalanceReconciler()
        assert reconciler._contracts_gateway is None

    def test_init_with_gateway(self):
        gateway = AsyncMock(spec=ContractsGateway)
        reconciler = BalanceReconciler(contracts_gateway=gateway)
        assert reconciler._contracts_gateway is gateway


class TestReconcileBalance:
    @pytest.mark.asyncio
    async def test_consistent(self):
        """When on-chain and local balances match, discrepancy should be near zero."""
        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(return_value=100.0)
        reconciler = BalanceReconciler(contracts_gateway=gateway)

        snapshot = await reconciler.reconcile_balance(
            token_id="0x123",
            owner="0xabc",
            local_balance=100.0,
        )
        assert snapshot.token_id == "0x123"
        assert snapshot.owner == "0xabc"
        assert snapshot.onchain_balance == 100.0
        assert snapshot.local_balance == 100.0
        assert snapshot.discrepancy < TOLERANCE

    @pytest.mark.asyncio
    async def test_discrepancy(self):
        """When on-chain and local balances differ, discrepancy should be positive."""
        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(return_value=100.0)
        reconciler = BalanceReconciler(contracts_gateway=gateway)

        snapshot = await reconciler.reconcile_balance(
            token_id="0x123",
            owner="0xabc",
            local_balance=80.0,
        )
        assert snapshot.onchain_balance == 100.0
        assert snapshot.local_balance == 80.0
        assert snapshot.discrepancy == 20.0

    @pytest.mark.asyncio
    async def test_unavailable_no_gateway(self):
        """When no gateway is set, onchain_balance is 0.0 and discrepancy equals local."""
        reconciler = BalanceReconciler()

        snapshot = await reconciler.reconcile_balance(
            token_id="0x123",
            owner="0xabc",
            local_balance=50.0,
        )
        assert snapshot.onchain_balance == 0.0
        assert snapshot.local_balance == 50.0
        assert snapshot.discrepancy == 50.0

    @pytest.mark.asyncio
    async def test_unavailable_on_error(self):
        """When balance_of raises, onchain_balance is 0.0 and discrepancy equals local."""
        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(side_effect=ConnectionError("rpc failed"))
        reconciler = BalanceReconciler(contracts_gateway=gateway)

        snapshot = await reconciler.reconcile_balance(
            token_id="0x123",
            owner="0xabc",
            local_balance=50.0,
        )
        assert snapshot.onchain_balance == 0.0
        assert snapshot.local_balance == 50.0
        assert snapshot.discrepancy == 50.0


class TestReconcilePositions:
    @pytest.mark.asyncio
    async def test_multiple_positions(self):
        """reconcile_positions returns a snapshot for each position in the dict."""
        gateway = AsyncMock(spec=ContractsGateway)

        async def balance_of(owner: str, token_id: str) -> float:
            lookup = {"t1": 100.0, "t2": 200.0}
            return lookup.get(token_id, 0.0)

        gateway.balance_of = AsyncMock(side_effect=balance_of)
        reconciler = BalanceReconciler(contracts_gateway=gateway)

        local_positions = {"t1": 100.0, "t2": 195.0}
        snapshots = await reconciler.reconcile_positions(
            local_positions=local_positions,
            owner="0xabc",
        )
        assert len(snapshots) == 2

        snapshots_by_id = {s.token_id: s for s in snapshots}
        assert snapshots_by_id["t1"].discrepancy < TOLERANCE
        assert snapshots_by_id["t2"].discrepancy == 5.0

    @pytest.mark.asyncio
    async def test_empty_positions(self):
        """An empty positions dict returns an empty list."""
        gateway = AsyncMock(spec=ContractsGateway)
        reconciler = BalanceReconciler(contracts_gateway=gateway)

        snapshots = await reconciler.reconcile_positions(
            local_positions={},
            owner="0xabc",
        )
        assert snapshots == []


class TestBalanceReconcilerClose:
    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        """close() should be safe to call multiple times."""
        gateway = AsyncMock(spec=ContractsGateway)
        gateway.close = AsyncMock()
        reconciler = BalanceReconciler(contracts_gateway=gateway)

        await reconciler.close()
        gateway.close.assert_called_once()

        # Second call should also succeed (idempotent)
        await reconciler.close()
        assert gateway.close.call_count == 2

    @pytest.mark.asyncio
    async def test_close_with_no_gateway(self):
        """close() should not error when no gateway was provided."""
        reconciler = BalanceReconciler()
        # Should not raise
        await reconciler.close()
