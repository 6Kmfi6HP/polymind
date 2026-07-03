"""
Automated recovery actions for fill-reconciliation discrepancies.

RecoveryManager evaluates reconciliation results and determines the next
action (ignore, retry, cancel-replace, escalate) based on fill status and
retry history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

from polymind.core.fills import FillEvent
from polymind.reconciliation.fills import (
    FillReconciliationRecord,
    ReconciliationStatus,
)


class RecoveryAction(Enum):
    """Recovery action to take for a discrepant fill."""

    IGNORE = auto()
    RETRY_ORDER = auto()
    CANCEL_REPLACE = auto()
    CLOSE_POSITION = auto()
    ESCALATE = auto()


@dataclass
class RecoveryRecord:
    """Record of a recovery action taken for a fill."""

    fill_id: str
    market_id: str
    issue: str
    action: RecoveryAction
    resolved: bool
    timestamp: datetime
    metadata: dict[str, str] = field(default_factory=dict)


class RecoveryManager:
    """Evaluate reconciliation results and determine recovery actions.

    Tracks retry counts per fill and escalates when the maximum number of
    retries has been exhausted.

    Parameters
    ----------
    max_retries:
        Maximum number of times a fill will be retried before escalation.
        Defaults to 3.
    """

    def __init__(self, max_retries: int = 3) -> None:
        self._max_retries = max_retries
        self._retry_counts: dict[str, int] = {}
        self._history: list[RecoveryRecord] = []

    async def assess(
        self,
        fill: FillEvent,
        reconciliation: FillReconciliationRecord,
    ) -> RecoveryAction:
        """Assess what recovery action to take based on reconciliation status.

        Parameters
        ----------
        fill:
            The fill event that was reconciled.
        reconciliation:
            The reconciliation record produced by ``FillReconciler``.

        Returns
        -------
        RecoveryAction
            The recommended action.
        """
        status = reconciliation.status

        if status == ReconciliationStatus.MATCHED:
            return RecoveryAction.IGNORE

        fill_id = fill.fill_id
        current_count = self._retry_counts.get(fill_id, 0)

        if current_count >= self._max_retries:
            return RecoveryAction.ESCALATE

        if status == ReconciliationStatus.MISSING:
            return RecoveryAction.RETRY_ORDER

        if status == ReconciliationStatus.MISMATCHED:
            return RecoveryAction.CANCEL_REPLACE

        # UNEXPECTED — not a fill we asked for, so no action
        return RecoveryAction.IGNORE

    async def execute(
        self,
        action: RecoveryAction,
        fill: FillEvent,
    ) -> bool:
        """Execute a recovery action and record it in history.

        Parameters
        ----------
        action:
            The recovery action to perform.
        fill:
            The fill event the action applies to.

        Returns
        -------
        bool
            True when the action is considered resolved, False otherwise.
        """
        issue: str
        resolved: bool

        if action == RecoveryAction.IGNORE:
            issue = "Fill reconciled successfully or no action required"
            resolved = True

        elif action == RecoveryAction.RETRY_ORDER:
            self._increment_retry(fill.fill_id)
            issue = "Fill missing — order will be retried"
            resolved = False

        elif action == RecoveryAction.CANCEL_REPLACE:
            self._increment_retry(fill.fill_id)
            issue = "Fill mismatched — order will be cancelled and replaced"
            resolved = False

        elif action == RecoveryAction.CLOSE_POSITION:
            issue = "Position will be closed to mitigate risk"
            resolved = False

        elif action == RecoveryAction.ESCALATE:
            issue = f"Max retries ({self._max_retries}) exceeded — escalation required"
            resolved = False

        else:
            issue = "Unknown recovery action"
            resolved = False

        record = RecoveryRecord(
            fill_id=fill.fill_id,
            market_id=fill.market_id,
            issue=issue,
            action=action,
            resolved=resolved,
            timestamp=datetime.now(),
        )
        self._history.append(record)
        return resolved

    def get_history(self) -> list[RecoveryRecord]:
        """Return the list of all recorded recovery actions.

        Returns
        -------
        list[RecoveryRecord]
            History of recovery actions in insertion order.
        """
        return list(self._history)

    async def close(self) -> None:
        """Release internal state. Idempotent."""
        self._history.clear()
        self._retry_counts.clear()

    def _increment_retry(self, fill_id: str) -> None:
        """Increment the retry counter for a given fill."""
        self._retry_counts[fill_id] = self._retry_counts.get(fill_id, 0) + 1
