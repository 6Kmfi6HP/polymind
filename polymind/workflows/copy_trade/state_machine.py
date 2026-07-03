"""
Copy Trade workflow state machine.

Monitors target wallet trades and replicates them proportionally.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum, auto


class CopyTradeState(Enum):
    IDLE = auto()
    MONITORING = auto()
    TRADE_DETECTED = auto()
    ANALYZING = auto()
    PLACING_ORDER = auto()
    AWAITING_FILL = auto()
    COMPLETED = auto()
    FAILED = auto()
    HALTED = auto()


class CopyTradeEvent(Enum):
    START = auto()
    TARGET_TRADE = auto()
    ANALYSIS_DONE = auto()
    ORDER_PLACED = auto()
    FILL_DETECTED = auto()
    ERROR = auto()
    HALT = auto()
    RESUME = auto()


TRANSITIONS: dict[CopyTradeState, dict[CopyTradeEvent, CopyTradeState]] = {
    CopyTradeState.IDLE: {
        CopyTradeEvent.START: CopyTradeState.MONITORING,
        CopyTradeEvent.HALT: CopyTradeState.HALTED,
    },
    CopyTradeState.MONITORING: {
        CopyTradeEvent.TARGET_TRADE: CopyTradeState.TRADE_DETECTED,
        CopyTradeEvent.HALT: CopyTradeState.HALTED,
    },
    CopyTradeState.TRADE_DETECTED: {
        CopyTradeEvent.ANALYSIS_DONE: CopyTradeState.PLACING_ORDER,
        CopyTradeEvent.ERROR: CopyTradeState.FAILED,
    },
    CopyTradeState.PLACING_ORDER: {
        CopyTradeEvent.ORDER_PLACED: CopyTradeState.AWAITING_FILL,
        CopyTradeEvent.ERROR: CopyTradeState.FAILED,
    },
    CopyTradeState.AWAITING_FILL: {
        CopyTradeEvent.FILL_DETECTED: CopyTradeState.AWAITING_FILL,
        CopyTradeEvent.TARGET_TRADE: CopyTradeState.MONITORING,
        CopyTradeEvent.ERROR: CopyTradeState.FAILED,
    },
    CopyTradeState.HALTED: {
        CopyTradeEvent.RESUME: CopyTradeState.IDLE,
    },
}


class CopyTradeStateMachine:
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.state: CopyTradeState = CopyTradeState.IDLE
        self.history: list[tuple[CopyTradeState, CopyTradeEvent, datetime]] = []
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = self.created_at

    def transition(self, event: CopyTradeEvent) -> CopyTradeState:
        allowed = TRANSITIONS.get(self.state, {})
        next_state = allowed.get(event)
        if next_state is None:
            raise ValueError(
                f"Invalid transition: {self.state.name} -> {event.name} "
                f"(workflow {self.workflow_id})"
            )
        self.history.append((self.state, event, datetime.now(timezone.utc)))
        self.state = next_state
        self.updated_at = datetime.now(timezone.utc)
        return self.state

    def can_transition(self, event: CopyTradeEvent) -> bool:
        return event in TRANSITIONS.get(self.state, {})

    def is_terminal(self) -> bool:
        return self.state in (CopyTradeState.COMPLETED, CopyTradeState.FAILED)

    def is_active(self) -> bool:
        return self.state not in (
            CopyTradeState.COMPLETED,
            CopyTradeState.FAILED,
            CopyTradeState.HALTED,
        )

    def reset(self) -> None:
        self.state = CopyTradeState.IDLE
        self.history = []
        self.updated_at = datetime.now(timezone.utc)
