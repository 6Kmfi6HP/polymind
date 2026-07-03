"""
Fill reconciliation between expected and actual fills.

FillReconciler compares expected fills (from strategy/paper execution) against
actual fills reported by the Polymarket WebSocket and CLOB API, producing
reconciliation records that highlight discrepancies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from polymind.core.fills import FillEvent
from polymind.polymarket.client import PolymarketClient
from polymind.polymarket.websocket import PolymarketWebSocketAdapter


class ReconciliationStatus(Enum):
    """Outcome of comparing an expected fill against actual data."""

    MATCHED = auto()
    MISMATCHED = auto()
    MISSING = auto()
    UNEXPECTED = auto()


@dataclass
class FillReconciliationRecord:
    """Result of reconciling a single expected fill against actual fill data."""

    market_id: str
    identity_string: str
    expected_fill_size: float
    expected_fill_price: float
    actual_fill_size: float
    actual_fill_price: float
    status: ReconciliationStatus
    discrepancy: float  # absolute difference in size
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class FillReconciler:
    """Compare expected fills against actual fill data from exchange sources.

    Uses the WebSocket adapter and/or CLOB API client to retrieve actual
    fills and compare them against the fills expected by the strategy or
    paper executor.

    Parameters
    ----------
    websocket_adapter:
        Optional WebSocket adapter for real-time fill events.
    clob_client:
        Optional Polymarket CLOB client for querying fill history.
    """

    def __init__(
        self,
        websocket_adapter: PolymarketWebSocketAdapter | None = None,
        clob_client: PolymarketClient | None = None,
    ) -> None:
        self._websocket_adapter = websocket_adapter
        self._clob_client = clob_client

    async def reconcile_fills(
        self,
        expected_fills: list[FillEvent],
        market_id: str,
    ) -> list[FillReconciliationRecord]:
        """Reconcile a batch of expected fills for a market.

        Each expected fill is checked against actual fill data retrieved
        from the CLOB client.  Any actual fills that have no corresponding
        expected fill are reported as ``UNEXPECTED``.
        """
        records: list[FillReconciliationRecord] = []
        actual_fills = await self._fetch_actual_fills(market_id)

        # Check each expected fill
        for expected in expected_fills:
            record = await self.reconcile_single(expected)
            records.append(record)

        # Detect unexpected actual fills that were not in the expected list
        expected_ids: set[str] = {e.fill_id for e in expected_fills}
        for actual in actual_fills:
            if actual.fill_id not in expected_ids:
                records.append(
                    FillReconciliationRecord(
                        market_id=actual.market_id,
                        identity_string=actual.order_id or actual.fill_id,
                        expected_fill_size=0.0,
                        expected_fill_price=0.0,
                        actual_fill_size=actual.size,
                        actual_fill_price=actual.price,
                        status=ReconciliationStatus.UNEXPECTED,
                        discrepancy=actual.size,
                        timestamp=actual.timestamp,
                    )
                )

        return records

    async def reconcile_single(
        self,
        expected: FillEvent,
    ) -> FillReconciliationRecord:
        """Reconcile a single expected fill against actual data.

        Looks up the actual fill by matching ``fill_id`` or ``order_id``.
        Returns a ``MATCHED``, ``MISMATCHED``, or ``MISSING`` record.
        """
        actual_fills = await self._fetch_actual_fills(expected.market_id)

        # Find a matching actual fill by fill_id, then by order_id
        match: FillEvent | None = None
        for actual in actual_fills:
            if actual.fill_id == expected.fill_id:
                match = actual
                break
            if (
                expected.order_id
                and actual.order_id == expected.order_id
                and abs(actual.price - expected.price) < 0.0001
            ):
                match = actual
                break

        if match is None:
            return FillReconciliationRecord(
                market_id=expected.market_id,
                identity_string=expected.order_id or expected.fill_id,
                expected_fill_size=expected.size,
                expected_fill_price=expected.price,
                actual_fill_size=0.0,
                actual_fill_price=0.0,
                status=ReconciliationStatus.MISSING,
                discrepancy=expected.size,
                timestamp=expected.timestamp,
            )

        discrepancy = abs(match.size - expected.size)
        if discrepancy < 0.0001 and abs(match.price - expected.price) < 0.0001:
            status = ReconciliationStatus.MATCHED
        else:
            status = ReconciliationStatus.MISMATCHED

        return FillReconciliationRecord(
            market_id=expected.market_id,
            identity_string=match.order_id or match.fill_id,
            expected_fill_size=expected.size,
            expected_fill_price=expected.price,
            actual_fill_size=match.size,
            actual_fill_price=match.price,
            status=status,
            discrepancy=discrepancy,
            timestamp=expected.timestamp,
        )

    def cross_check_fills(
        self,
        websocket_fills: list[FillEvent],
        clob_fills: list[FillEvent],
    ) -> list[FillReconciliationRecord]:
        """Cross-check fills from two sources, reporting discrepancies.

        Compares websocket-reported fills against CLOB API-reported fills.
        Returns records for mismatches and fills unique to one source.
        """
        records: list[FillReconciliationRecord] = []
        clob_by_id: dict[str, FillEvent] = {f.fill_id: f for f in clob_fills}

        for ws_fill in websocket_fills:
            clob_fill = clob_by_id.pop(ws_fill.fill_id, None)
            if clob_fill is None:
                records.append(
                    FillReconciliationRecord(
                        market_id=ws_fill.market_id,
                        identity_string=ws_fill.order_id or ws_fill.fill_id,
                        expected_fill_size=ws_fill.size,
                        expected_fill_price=ws_fill.price,
                        actual_fill_size=0.0,
                        actual_fill_price=0.0,
                        status=ReconciliationStatus.UNEXPECTED,
                        discrepancy=ws_fill.size,
                        timestamp=ws_fill.timestamp,
                    )
                )
                continue

            discrepancy = abs(ws_fill.size - clob_fill.size)
            if discrepancy < 0.0001 and abs(ws_fill.price - clob_fill.price) < 0.0001:
                records.append(
                    FillReconciliationRecord(
                        market_id=ws_fill.market_id,
                        identity_string=ws_fill.order_id or ws_fill.fill_id,
                        expected_fill_size=ws_fill.size,
                        expected_fill_price=ws_fill.price,
                        actual_fill_size=clob_fill.size,
                        actual_fill_price=clob_fill.price,
                        status=ReconciliationStatus.MATCHED,
                        discrepancy=0.0,
                        timestamp=ws_fill.timestamp,
                    )
                )
            else:
                records.append(
                    FillReconciliationRecord(
                        market_id=ws_fill.market_id,
                        identity_string=ws_fill.order_id or ws_fill.fill_id,
                        expected_fill_size=ws_fill.size,
                        expected_fill_price=ws_fill.price,
                        actual_fill_size=clob_fill.size,
                        actual_fill_price=clob_fill.price,
                        status=ReconciliationStatus.MISMATCHED,
                        discrepancy=discrepancy,
                        timestamp=ws_fill.timestamp,
                    )
                )

        # Remaining CLOB fills have no WebSocket counterpart
        ws_ids = {f.fill_id for f in websocket_fills}
        for clob_fill in clob_fills:
            if clob_fill.fill_id not in ws_ids:
                records.append(
                    FillReconciliationRecord(
                        market_id=clob_fill.market_id,
                        identity_string=clob_fill.order_id or clob_fill.fill_id,
                        expected_fill_size=0.0,
                        expected_fill_price=0.0,
                        actual_fill_size=clob_fill.size,
                        actual_fill_price=clob_fill.price,
                        status=ReconciliationStatus.UNEXPECTED,
                        discrepancy=clob_fill.size,
                        timestamp=clob_fill.timestamp,
                    )
                )

        return records

    async def _fetch_actual_fills(
        self,
        market_id: str,
    ) -> list[FillEvent]:
        """Retrieve actual fills from the CLOB client."""
        if self._clob_client is not None:
            try:
                raw_fills = await self._clob_client.get_fills(market_id=market_id)
                return list(raw_fills or [])
            except (AttributeError, NotImplementedError):
                pass
        return []

    async def close(self) -> None:
        """Close underlying connections. Idempotent."""
        if self._websocket_adapter is not None:
            await self._websocket_adapter.close()
