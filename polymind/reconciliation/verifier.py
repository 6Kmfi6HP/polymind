"""
Three-way fill verification — on-chain balance as ultimate truth.

Integrates expected fills (from strategy/paper), WebSocket fill events,
CLOB API fills, and on-chain ERC-1155 balance to detect ghost fills
and verify fill status.

WebSocket events are wake-up signals (not truth).
CLOB API fills are cross-checks.
On-chain ERC-1155 balanceOf via RPC is the ultimate truth.

Reference: pm-terminal-all-in-one (ghost-fill recovery pattern)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from polymind.core.fills import FillEvent
from polymind.polymarket.contracts import ContractsGateway
from polymind.reconciliation.balances import BalanceReconciler, BalanceSnapshot
from polymind.reconciliation.fills import (
    FillReconciler,
    FillReconciliationRecord,
    ReconciliationStatus,
)


class FillVerificationStatus(Enum):
    """Status of a fill after three-way verification.

    CONFIRMED:
        The fill is present in expected fills (or WebSocket/CLOB) AND
        confirmed by on-chain balance change.
    GHOST:
        On-chain balance change confirms a fill occurred, but there is
        no corresponding expected fill, WebSocket event, or CLOB record.
        A synthetic fill should be created to match on-chain state.
    MISSING:
        The fill was expected (or reported by WebSocket/CLOB) but the
        on-chain balance shows no corresponding change.
    DISCREPANCY:
        The fill is present in multiple sources but with conflicting
        size or price that cannot be resolved.
    UNVERIFIED:
        On-chain balance data is unavailable (no gateway or RPC error),
        so the fill cannot be confirmed or refuted on-chain.
    """

    CONFIRMED = auto()
    GHOST = auto()
    MISSING = auto()
    DISCREPANCY = auto()
    UNVERIFIED = auto()


@dataclass
class FillVerificationResult:
    """Result of three-way verification for a single fill or balance delta.

    Parameters
    ----------
    fill_id:
        The fill identifier, or a synthetic ID for ghost fills.
    market_id:
        The market the fill belongs to.
    token_id:
        The ERC-1155 token identifier (can be derived from market + outcome).
    status:
        Verification status.
    expected_size:
        Size from expected fill / WebSocket / CLOB (0.0 for ghost fills).
    onchain_delta:
        Change in on-chain balance observed during the verification window.
    confidence:
        How many of the three sources agree (0-3).
    reconciliation_record:
        Optional FillReconciliationRecord from WebSocket-vs-CLOB cross-check.
    balance_snapshot:
        Optional BalanceSnapshot from on-chain balance check.
    synthetic_fill:
        If status is GHOST, a FillEvent that should be created to reconcile
        local state with on-chain truth.
    timestamp:
        When the verification was performed.
    metadata:
        Extra diagnostic information.
    """

    fill_id: str
    market_id: str
    token_id: str
    status: FillVerificationStatus
    expected_size: float
    onchain_delta: float
    confidence: int
    reconciliation_record: FillReconciliationRecord | None = None
    balance_snapshot: BalanceSnapshot | None = None
    synthetic_fill: FillEvent | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


class ThreeWayFillVerifier:
    """Verify fills by cross-referencing expected/WebSocket/CLOB with on-chain balance.

    Integrates the previously separate FillReconciler (WebSocket-vs-CLOB) and
    BalanceReconciler (on-chain-vs-local) into a single three-way verification
    that uses on-chain balance as the ultimate truth source.

    Parameters
    ----------
    contracts_gateway:
        Optional ContractsGateway for querying on-chain balances.
        When None, all verifications return UNVERIFIED (no on-chain truth
        available), which is suitable for paper/simulation mode.
    fill_reconciler:
        Optional FillReconciler for WebSocket-vs-CLOB cross-check.
        Created with default (None, None) if not provided.
    balance_reconciler:
        Optional BalanceReconciler for on-chain balance checks.
        Created from contracts_gateway if not provided.
    tolerance:
        Tolerance for comparing balance deltas (default 0.001).
    """

    def __init__(
        self,
        contracts_gateway: ContractsGateway | None = None,
        fill_reconciler: FillReconciler | None = None,
        balance_reconciler: BalanceReconciler | None = None,
        tolerance: float = 0.001,
    ) -> None:
        self._fill_reconciler = fill_reconciler or FillReconciler()
        self._balance_reconciler = balance_reconciler or BalanceReconciler(
            contracts_gateway=contracts_gateway,
        )
        self._contracts_gateway = contracts_gateway
        self._tolerance = tolerance

    async def verify_fill(
        self,
        fill: FillEvent,
        owner: str,
        token_id: str,
        onchain_balance_before: float | None = None,
    ) -> FillVerificationResult:
        """Verify a single fill using all three sources.

        The verification process:
        1. Cross-check the fill's WebSocket/CLOB status via ``fill_reconciler``.
        2. Compare on-chain balance after the fill against expected post-fill balance.
        3. Classify the fill as CONFIRMED, GHOST, MISSING, or DISCREPANCY.

        Parameters
        ----------
        fill:
            The fill event to verify.
        owner:
            The wallet address to check on-chain balance for.
        token_id:
            The ERC-1155 token ID for the fill outcome.
        onchain_balance_before:
            Optional on-chain balance *before* the fill occurred. When provided,
            the delta is computed as ``current_balance - balance_before``. When
            ``None``, the expected post-fill balance is estimated from the fill size.

        Returns
        -------
        FillVerificationResult
            Verdict with CONFIRMED / GHOST / MISSING / DISCREPANCY / UNVERIFIED.
        """
        # Step 1: Cross-check with CLOB via FillReconciler
        clob_record = await self._cross_check_single(fill)

        # Step 2: Check on-chain balance
        balance = await self._balance_reconciler.reconcile_balance(
            token_id=token_id,
            owner=owner,
            local_balance=fill.size,
        )

        # Step 3: Compute on-chain delta
        onchain_delta: float = 0.0
        if onchain_balance_before is not None:
            # We have a before-snapshot — compute actual delta
            onchain_delta = max(0.0, balance.onchain_balance - onchain_balance_before)
        elif balance.onchain_balance > self._tolerance:
            # No before-snapshot, but we can see the after-state.
            # Assume the fill size is the delta (conservative).
            onchain_delta = balance.onchain_balance
        else:
            onchain_delta = 0.0

        # Step 4: Classify
        gateway_unavailable = self._contracts_gateway is None
        onchain_empty = onchain_delta < self._tolerance
        onchain_matches = abs(onchain_delta - fill.size) < self._tolerance
        expected_missing = (
            clob_record is not None and clob_record.status == ReconciliationStatus.MISSING
        )

        if gateway_unavailable or (
            balance.onchain_balance == 0.0 and onchain_balance_before is None
        ):
            # Cannot reach on-chain truth
            status = FillVerificationStatus.UNVERIFIED
            confidence = (
                1 if clob_record and clob_record.status in (ReconciliationStatus.MATCHED,) else 0
            )
        elif onchain_matches and not expected_missing:
            status = FillVerificationStatus.CONFIRMED
            confidence = (
                3 if clob_record and clob_record.status == ReconciliationStatus.MATCHED else 2
            )
        elif onchain_empty and expected_missing:
            # Expected by strategy, but not visible on-chain or in CLOB
            status = FillVerificationStatus.MISSING
            confidence = 0
        elif (
            onchain_empty and clob_record and clob_record.status == ReconciliationStatus.UNEXPECTED
        ):
            # WebSocket said fill, but CLOB and on-chain disagree
            status = FillVerificationStatus.MISSING
            confidence = 0
        elif onchain_matches and expected_missing:
            # On-chain confirms a fill, but no expected/WebSocket/CLOB record — GHOST
            status = FillVerificationStatus.GHOST
            confidence = 1
            # Create synthetic fill for local state reconciliation
            self._maybe_create_synthetic_fill(fill, token_id)
        elif not onchain_matches and not onchain_empty:
            # On-chain shows some change, but not matching our fill size
            status = FillVerificationStatus.DISCREPANCY
            confidence = 1
        else:
            status = FillVerificationStatus.UNVERIFIED
            confidence = 0

        return FillVerificationResult(
            fill_id=fill.fill_id,
            market_id=fill.market_id,
            token_id=token_id,
            status=status,
            expected_size=fill.size,
            onchain_delta=onchain_delta,
            confidence=confidence,
            reconciliation_record=clob_record,
            balance_snapshot=balance if not gateway_unavailable else None,
            synthetic_fill=self._synthetic if status == FillVerificationStatus.GHOST else None,
        )

    async def detect_ghost_fills(
        self,
        expected_fills: list[FillEvent],
        ws_fills: list[FillEvent],
        clob_fills: list[FillEvent],
        owner: str,
        token_id: str,
        expected_post_balance: float = 0.0,
    ) -> list[FillVerificationResult]:
        """Detect ghost fills by comparing on-chain balance against all sources.

        A ghost fill is a fill confirmed by on-chain balance change that has
        no corresponding entry in any of: expected fills, WebSocket events,
        or CLOB API fills.

        Parameters
        ----------
        expected_fills:
            Fills expected by the strategy or paper executor.
        ws_fills:
            Fills reported by WebSocket events.
        clob_fills:
            Fills reported by the CLOB API.
        owner:
            The wallet address to query on-chain.
        token_id:
            The ERC-1155 token ID to check.
        expected_post_balance:
            Expected total on-chain balance after all fills. If 0.0, the
            total on-chain balance at snapshot time is used as baseline.

        Returns
        -------
        list[FillVerificationResult]
            List of ghost fill results (empty if none detected).
        """
        if self._contracts_gateway is None:
            return []

        # Get current on-chain balance
        balance = await self._balance_reconciler.reconcile_balance(
            token_id=token_id,
            owner=owner,
            local_balance=expected_post_balance,
        )

        # Compute expected total size from known fills
        expected_total = sum(f.size for f in expected_fills) if expected_fills else 0.0

        ghost_size = max(0.0, balance.onchain_balance - expected_total)
        ghost_detected = ghost_size > self._tolerance

        if not ghost_detected:
            return []

        # Create a synthetic ghost fill
        ghost_fill = FillEvent(
            fill_id=f"ghost-{token_id}-{datetime.now().isoformat()}",
            market_id=expected_fills[0].market_id if expected_fills else token_id,
            outcome="",
            side=ws_fills[0].side if ws_fills else clob_fills[0].side if clob_fills else None,  # type: ignore[arg-type]
            price=0.0,
            size=ghost_size,
            fee=0.0,
            timestamp=datetime.now(),
            source=ws_fills[0].source if ws_fills else clob_fills[0].source if clob_fills else None,  # type: ignore[arg-type]
        )

        return [
            FillVerificationResult(
                fill_id=ghost_fill.fill_id,
                market_id=ghost_fill.market_id or "",
                token_id=token_id,
                status=FillVerificationStatus.GHOST,
                expected_size=0.0,
                onchain_delta=ghost_size,
                confidence=1,
                synthetic_fill=ghost_fill,
            )
        ]

    async def verify_fills_batch(
        self,
        fills: list[FillEvent],
        owner: str,
        token_id: str,
        onchain_balance_before: float | None = None,
    ) -> list[FillVerificationResult]:
        """Verify a batch of fills against on-chain balance.

        Parameters
        ----------
        fills:
            List of fill events to verify.
        owner:
            Wallet address for on-chain queries.
        token_id:
            ERC-1155 token ID.
        onchain_balance_before:
            Optional pre-fill balance snapshot.

        Returns
        -------
        list[FillVerificationResult]
            One result per fill.
        """
        results: list[FillVerificationResult] = []
        for fill in fills:
            result = await self.verify_fill(
                fill=fill,
                owner=owner,
                token_id=token_id,
                onchain_balance_before=onchain_balance_before,
            )
            results.append(result)
        return results

    async def close(self) -> None:
        """Release underlying connections. Idempotent."""
        if self._fill_reconciler is not None:
            await self._fill_reconciler.close()
        if self._balance_reconciler is not None:
            await self._balance_reconciler.close()

    # ── Internal helpers ──────────────────────────────────────────────────

    def _maybe_create_synthetic_fill(
        self,
        fill: FillEvent,
        token_id: str,
    ) -> None:
        """Create a synthetic FillEvent for a ghost fill."""
        self._synthetic = FillEvent(
            fill_id=f"synthetic-{fill.fill_id}",
            market_id=fill.market_id,
            outcome="YES",
            side=fill.side,
            price=fill.price,
            size=fill.size,
            fee=0.0,
            timestamp=datetime.now(),
            source=fill.source,
            order_id=fill.order_id,
            metadata={"synthetic": True, "ghost_fill": True},
        )

    async def _cross_check_single(
        self,
        fill: FillEvent,
    ) -> FillReconciliationRecord | None:
        """Cross-check a single fill via FillReconciler."""
        if self._fill_reconciler is None:
            return None
        try:
            return await self._fill_reconciler.reconcile_single(fill)
        except (AttributeError, NotImplementedError):
            return None
