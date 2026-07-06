"""
Maker Rebate workflow state machine.

The Maker Rebate workflow fills YES and NO orders, then merges/redeems
the paired positions for profit. State transitions track the lifecycle
from order placement through settlement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum, auto


class RebateState(Enum):
    """Lifecycle states for a Maker Rebate workflow instance."""

    IDLE = auto()
    PLACING_ORDERS = auto()
    AWAITING_FILLS = auto()
    FILLS_COMPLETE = auto()
    MERGING = auto()
    REDEEMING = auto()
    COMPLETED = auto()
    FAILED = auto()
    HALTED = auto()


class RebateEvent(Enum):
    """Events that trigger state transitions."""

    START = auto()
    ORDERS_PLACED = auto()
    FILL_DETECTED = auto()
    ALL_FILLED = auto()
    MERGE_DONE = auto()
    REDEEM_DONE = auto()
    ERROR = auto()
    HALT = auto()
    RESUME = auto()


TRANSITIONS: dict[RebateState, dict[RebateEvent, RebateState]] = {
    RebateState.IDLE: {
        RebateEvent.START: RebateState.PLACING_ORDERS,
        RebateEvent.HALT: RebateState.HALTED,
    },
    RebateState.PLACING_ORDERS: {
        RebateEvent.ORDERS_PLACED: RebateState.AWAITING_FILLS,
        RebateEvent.ERROR: RebateState.FAILED,
        RebateEvent.HALT: RebateState.HALTED,
    },
    RebateState.AWAITING_FILLS: {
        RebateEvent.FILL_DETECTED: RebateState.AWAITING_FILLS,
        RebateEvent.ALL_FILLED: RebateState.FILLS_COMPLETE,
        RebateEvent.ERROR: RebateState.FAILED,
        RebateEvent.HALT: RebateState.HALTED,
    },
    RebateState.FILLS_COMPLETE: {
        RebateEvent.MERGE_DONE: RebateState.MERGING,
        RebateEvent.HALT: RebateState.HALTED,
    },
    RebateState.MERGING: {
        RebateEvent.REDEEM_DONE: RebateState.REDEEMING,
        RebateEvent.ERROR: RebateState.FAILED,
    },
    RebateState.REDEEMING: {
        RebateEvent.REDEEM_DONE: RebateState.COMPLETED,
        RebateEvent.ERROR: RebateState.FAILED,
    },
    RebateState.HALTED: {
        RebateEvent.RESUME: RebateState.IDLE,
    },
}


class RebateStateMachine:
    """State machine for a single Maker Rebate workflow instance."""

    def __init__(self, workflow_id: str, paper_mode: bool = False):
        self.workflow_id = workflow_id
        self.paper_mode = paper_mode
        self.state: RebateState = RebateState.IDLE
        self.history: list[tuple[RebateState, RebateEvent, datetime]] = []
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = self.created_at

    def transition(self, event: RebateEvent) -> RebateState:
        """Apply an event and transition to the next state.

        Returns the new state. Raises ValueError if the transition is invalid.
        """
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

    def can_transition(self, event: RebateEvent) -> bool:
        """Check if a transition is valid without applying it."""
        return event in TRANSITIONS.get(self.state, {})

    def is_terminal(self) -> bool:
        """Check if the state machine has reached a terminal state."""
        return self.state in (RebateState.COMPLETED, RebateState.FAILED)

    def is_active(self) -> bool:
        """Check if the workflow is still active (not terminal/halted)."""
        return self.state not in (
            RebateState.COMPLETED,
            RebateState.FAILED,
            RebateState.HALTED,
        )

    @property
    def is_paper_mode(self) -> bool:
        """Whether this workflow is running in paper/simulation mode."""
        return self.paper_mode

    def reset(self) -> None:
        """Reset the state machine to IDLE."""
        self.state = RebateState.IDLE
        self.history = []
        self.updated_at = datetime.now(timezone.utc)
