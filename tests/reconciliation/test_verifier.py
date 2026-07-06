"""
Tests for ThreeWayFillVerifier and related domain types.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import OrderSide
from polymind.polymarket.contracts import ContractsGateway
from polymind.reconciliation.balances import BalanceReconciler
from polymind.reconciliation.fills import FillReconciler
from polymind.reconciliation.verifier import (
    FillVerificationResult,
    FillVerificationStatus,
    ThreeWayFillVerifier,
)

TOLERANCE = 0.001


# ── FillVerificationStatus ──────────────────────────────────────────────────


class TestFillVerificationStatus:
    def test_enum_values_are_distinct(self):
        values = list(FillVerificationStatus)
        assert len(values) == len(set(values))

    def test_all_statuses_defined(self):
        expected = {"CONFIRMED", "GHOST", "MISSING", "DISCREPANCY", "UNVERIFIED"}
        assert {e.name for e in FillVerificationStatus} == expected


# ── FillVerificationResult ──────────────────────────────────────────────────


class TestFillVerificationResult:
    def test_minimal_construction(self):
        result = FillVerificationResult(
            fill_id="fill-001",
            market_id="0xabc",
            token_id="0xtoken123",
            status=FillVerificationStatus.CONFIRMED,
            expected_size=10.0,
            onchain_delta=10.0,
            confidence=3,
        )
        assert result.fill_id == "fill-001"
        assert result.market_id == "0xabc"
        assert result.token_id == "0xtoken123"
        assert result.status == FillVerificationStatus.CONFIRMED
        assert result.expected_size == 10.0
        assert result.onchain_delta == 10.0
        assert result.confidence == 3
        assert result.reconciliation_record is None
        assert result.balance_snapshot is None
        assert result.synthetic_fill is None
        assert result.metadata == {}

    def test_ghost_result_contains_synthetic_fill(self):
        synthetic = FillEvent(
            fill_id="synthetic-ghost-001",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.50,
            size=5.0,
            fee=0.0,
            timestamp=datetime.now(),
            source=FillSource.ONCHAIN,
        )
        result = FillVerificationResult(
            fill_id="ghost-001",
            market_id="0xabc",
            token_id="0xtoken123",
            status=FillVerificationStatus.GHOST,
            expected_size=0.0,
            onchain_delta=5.0,
            confidence=1,
            synthetic_fill=synthetic,
        )
        assert result.status == FillVerificationStatus.GHOST
        assert result.synthetic_fill is not None
        assert result.synthetic_fill.fill_id == "synthetic-ghost-001"
        assert result.synthetic_fill.size == 5.0

    def test_unverified_result_minimal_confidence(self):
        result = FillVerificationResult(
            fill_id="fill-002",
            market_id="0xdef",
            token_id="0xtoken456",
            status=FillVerificationStatus.UNVERIFIED,
            expected_size=10.0,
            onchain_delta=0.0,
            confidence=0,
        )
        assert result.status == FillVerificationStatus.UNVERIFIED
        assert result.confidence == 0


# ── ThreeWayFillVerifier Init ──────────────────────────────────────────────


class TestThreeWayFillVerifierInit:
    def test_init_with_no_gateway(self):
        """Without a gateway, the verifier can still cross-check fills."""
        verifier = ThreeWayFillVerifier()
        assert verifier._contracts_gateway is None
        assert verifier._fill_reconciler is not None
        assert verifier._balance_reconciler is not None

    def test_init_with_gateway(self):
        """With a gateway, on-chain verification becomes available."""
        gateway = MagicMock(spec=ContractsGateway)
        verifier = ThreeWayFillVerifier(contracts_gateway=gateway)
        assert verifier._contracts_gateway is gateway
        assert verifier._balance_reconciler._contracts_gateway is gateway

    def test_init_with_custom_reconcilers(self):
        """Custom reconcilers can be injected for testing."""
        fill_reconciler = MagicMock(spec=FillReconciler)
        balance_reconciler = MagicMock(spec=BalanceReconciler)
        verifier = ThreeWayFillVerifier(
            fill_reconciler=fill_reconciler,
            balance_reconciler=balance_reconciler,
        )
        assert verifier._fill_reconciler is fill_reconciler
        assert verifier._balance_reconciler is balance_reconciler

    def test_custom_tolerance(self):
        """Custom tolerance should be stored."""
        verifier = ThreeWayFillVerifier(tolerance=0.01)
        assert verifier._tolerance == 0.01


# ── Verify Fill ────────────────────────────────────────────────────────────


class TestVerifyFill:
    @pytest.mark.asyncio
    async def test_verify_fill_confirmed_all_sources(self):
        """A fill present in expected fills, CLOB, and on-chain should be CONFIRMED."""
        now = datetime.now()
        fill = FillEvent(
            fill_id="fill-001",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.WEBSOCKET,
            order_id="ord-001",
        )
        # Mock CLOB client to return matching fill
        clob = AsyncMock()
        clob.get_fills = AsyncMock(return_value=[fill])
        fill_reconciler = FillReconciler(clob_client=clob)

        # Mock contracts gateway to return matching on-chain balance
        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(return_value=10.0)

        verifier = ThreeWayFillVerifier(
            contracts_gateway=gateway,
            fill_reconciler=fill_reconciler,
        )

        result = await verifier.verify_fill(
            fill=fill,
            owner="0xowner",
            token_id="0xtoken123",
            onchain_balance_before=0.0,
        )

        assert result.status == FillVerificationStatus.CONFIRMED
        assert result.confidence >= 2
        assert result.fill_id == "fill-001"
        assert result.expected_size == 10.0
        assert result.onchain_delta >= 9.999  # within tolerance

    @pytest.mark.asyncio
    async def test_verify_fill_ghost_onchain_no_expected(self):
        """A fill present on-chain but missing from expected/CLOB should be GHOST."""
        now = datetime.now()
        fill = FillEvent(
            fill_id="fill-002",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.SIMULATED,
        )

        # CLOB returns no fills (fill is missing)
        clob = AsyncMock()
        clob.get_fills = AsyncMock(return_value=[])
        fill_reconciler = FillReconciler(clob_client=clob)

        # On-chain shows the fill occurred
        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(return_value=10.0)

        verifier = ThreeWayFillVerifier(
            contracts_gateway=gateway,
            fill_reconciler=fill_reconciler,
        )

        result = await verifier.verify_fill(
            fill=fill,
            owner="0xowner",
            token_id="0xtoken123",
            onchain_balance_before=0.0,
        )

        # The fill is on-chain but missing from expected/CLOB → GHOST
        assert result.status == FillVerificationStatus.GHOST
        assert result.confidence == 1

    @pytest.mark.asyncio
    async def test_verify_fill_missing_onchain_empty(self):
        """A fill expected but not present on-chain should be MISSING."""
        now = datetime.now()
        fill = FillEvent(
            fill_id="fill-003",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.SIMULATED,
        )

        # CLOB returns no fills
        clob = AsyncMock()
        clob.get_fills = AsyncMock(return_value=[])
        fill_reconciler = FillReconciler(clob_client=clob)

        # On-chain shows no balance change
        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(return_value=0.0)

        verifier = ThreeWayFillVerifier(
            contracts_gateway=gateway,
            fill_reconciler=fill_reconciler,
        )

        result = await verifier.verify_fill(
            fill=fill,
            owner="0xowner",
            token_id="0xtoken123",
            onchain_balance_before=0.0,
        )

        assert result.status == FillVerificationStatus.MISSING
        assert result.confidence == 0

    @pytest.mark.asyncio
    async def test_verify_fill_unverified_no_gateway(self):
        """Without a gateway, status should be UNVERIFIED."""
        now = datetime.now()
        fill = FillEvent(
            fill_id="fill-004",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.SIMULATED,
        )

        # No gateway provided
        verifier = ThreeWayFillVerifier()

        result = await verifier.verify_fill(
            fill=fill,
            owner="0xowner",
            token_id="0xtoken123",
        )

        assert result.status == FillVerificationStatus.UNVERIFIED
        assert result.confidence == 0

    @pytest.mark.asyncio
    async def test_verify_fill_discrepancy_size_mismatch(self):
        """When on-chain delta does not match fill size, status should be DISCREPANCY."""
        now = datetime.now()
        fill = FillEvent(
            fill_id="fill-005",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.WEBSOCKET,
        )

        # CLOB matches
        clob = AsyncMock()
        clob.get_fills = AsyncMock(return_value=[fill])
        fill_reconciler = FillReconciler(clob_client=clob)

        # On-chain shows only 5.0 (half the expected fill)
        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(return_value=5.0)

        verifier = ThreeWayFillVerifier(
            contracts_gateway=gateway,
            fill_reconciler=fill_reconciler,
        )

        result = await verifier.verify_fill(
            fill=fill,
            owner="0xowner",
            token_id="0xtoken123",
            onchain_balance_before=0.0,
        )

        assert result.status == FillVerificationStatus.DISCREPANCY
        assert result.confidence == 1

    @pytest.mark.asyncio
    async def test_verify_fill_without_before_snapshot(self):
        """When onchain_balance_before is None, the verifier uses available data."""
        now = datetime.now()
        fill = FillEvent(
            fill_id="fill-006",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.WEBSOCKET,
        )

        clob = AsyncMock()
        clob.get_fills = AsyncMock(return_value=[fill])
        fill_reconciler = FillReconciler(clob_client=clob)

        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(return_value=10.0)

        verifier = ThreeWayFillVerifier(
            contracts_gateway=gateway,
            fill_reconciler=fill_reconciler,
        )

        # No before-snapshot provided — verifier falls back to current balance
        result = await verifier.verify_fill(
            fill=fill,
            owner="0xowner",
            token_id="0xtoken123",
        )

        # Without before-snapshot, gets UNVERIFIED because we can't compute delta
        # (onchain_balance 10.0 is treated as after-state, not as delta)
        assert result.status in (
            FillVerificationStatus.CONFIRMED,
            FillVerificationStatus.UNVERIFIED,
        )


# ── Detect Ghost Fills ──────────────────────────────────────────────────────


class TestDetectGhostFills:
    @pytest.mark.asyncio
    async def test_detect_no_ghost_when_fills_match(self):
        """When fill totals match on-chain balance, no ghost fills detected."""
        now = datetime.now()
        expected = [
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

        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(return_value=10.0)

        verifier = ThreeWayFillVerifier(contracts_gateway=gateway)

        ghosts = await verifier.detect_ghost_fills(
            expected_fills=expected,
            ws_fills=[],
            clob_fills=[],
            owner="0xowner",
            token_id="0xtoken123",
            expected_post_balance=10.0,
        )

        assert len(ghosts) == 0

    @pytest.mark.asyncio
    async def test_detect_ghost_when_balance_exceeds_expected(self):
        """When on-chain balance exceeds expected total, ghost fills detected."""
        now = datetime.now()
        expected = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=5.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.SIMULATED,
            ),
        ]

        gateway = AsyncMock(spec=ContractsGateway)
        # On-chain shows 15.0, but expected total is only 5.0 → 10.0 ghost
        gateway.balance_of = AsyncMock(return_value=15.0)

        verifier = ThreeWayFillVerifier(contracts_gateway=gateway)

        ghosts = await verifier.detect_ghost_fills(
            expected_fills=expected,
            ws_fills=[],
            clob_fills=[],
            owner="0xowner",
            token_id="0xtoken123",
            expected_post_balance=5.0,
        )

        assert len(ghosts) >= 1
        if ghosts:
            assert ghosts[0].status == FillVerificationStatus.GHOST
            assert ghosts[0].synthetic_fill is not None
            assert ghosts[0].onchain_delta >= 9.999  # ~10.0

    @pytest.mark.asyncio
    async def test_detect_ghost_no_gateway_returns_empty(self):
        """Without a gateway, ghost detection returns empty list."""
        verifier = ThreeWayFillVerifier()

        ghosts = await verifier.detect_ghost_fills(
            expected_fills=[],
            ws_fills=[],
            clob_fills=[],
            owner="0xowner",
            token_id="0xtoken123",
        )

        assert ghosts == []

    @pytest.mark.asyncio
    async def test_detect_ghost_with_ws_and_clob_fills(self):
        """Ghost detection considers all three sources (expected, WS, CLOB)."""
        now = datetime.now()
        ws_fills = [
            FillEvent(
                fill_id="ws-001",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=5.0,
                fee=0.01,
                timestamp=now,
                source=FillSource.WEBSOCKET,
            ),
        ]

        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(return_value=15.0)

        verifier = ThreeWayFillVerifier(contracts_gateway=gateway)

        # No expected or CLOB fills; WS fills total 5.0, on-chain shows 15.0
        ghosts = await verifier.detect_ghost_fills(
            expected_fills=[],
            ws_fills=ws_fills,
            clob_fills=[],
            owner="0xowner",
            token_id="0xtoken123",
            expected_post_balance=5.0,
        )

        # Ghost of 10.0 detected (15.0 on-chain - 5.0 WS total)
        assert len(ghosts) >= 1


# ── Verify Fills Batch ──────────────────────────────────────────────────────


class TestVerifyFillsBatch:
    @pytest.mark.asyncio
    async def test_batch_returns_one_result_per_fill(self):
        now = datetime.now()
        fills = [
            FillEvent(
                fill_id=f"fill-{i:03d}",
                market_id="0xabc",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.85,
                size=float(i),
                fee=0.001,
                timestamp=now,
                source=FillSource.SIMULATED,
            )
            for i in range(3)
        ]

        gateway = AsyncMock(spec=ContractsGateway)
        gateway.balance_of = AsyncMock(return_value=0.0)

        verifier = ThreeWayFillVerifier(contracts_gateway=gateway)

        results = await verifier.verify_fills_batch(
            fills=fills,
            owner="0xowner",
            token_id="0xtoken123",
            onchain_balance_before=0.0,
        )

        assert len(results) == len(fills)
        for r in results:
            assert isinstance(r, FillVerificationResult)

    @pytest.mark.asyncio
    async def test_batch_empty_list(self):
        verifier = ThreeWayFillVerifier()

        results = await verifier.verify_fills_batch(
            fills=[],
            owner="0xowner",
            token_id="0xtoken123",
        )

        assert results == []


# ── Close ───────────────────────────────────────────────────────────────────


class TestThreeWayFillVerifierClose:
    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        gateway = AsyncMock(spec=ContractsGateway)
        gateway.close = AsyncMock()
        verifier = ThreeWayFillVerifier(contracts_gateway=gateway)

        await verifier.close()
        await verifier.close()  # Second call should not raise

    @pytest.mark.asyncio
    async def test_close_with_no_gateway(self):
        verifier = ThreeWayFillVerifier()
        await verifier.close()  # Should not raise
