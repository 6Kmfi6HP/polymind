"""
Sniper workflow state machine.

Monitors markets for deep discount opportunities, triggering buy orders
when price drops far below fair value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Dict, List


class SniperState(Enum):
    IDLE = auto()
    WATCHING = auto()
    OPPORTUNITY_DETECTED = auto()
    PLACING_ORDER = auto()
    AWAITING_FILL = auto()
    COMPLETED = auto()
    FAILED = auto()
    HALTED = auto()


class SniperEvent(Enum):
    START = auto()
    DISCOUNT_SIGNAL = auto()
    ORDER_PLACED = auto()
    FILL_DETECTED = auto()
    POSITION_SOLD = auto()
    ERROR = auto()
    HALT = auto()
    RESUME = auto()


TRANSITIONS: Dict[SniperState, Dict[SniperEvent, SniperState]] = {
    SniperState.IDLE: {
        SniperEvent.START: SniperState.WATCHING,
        SniperEvent.HALT: SniperState.HALTED,
    },
    SniperState.WATCHING: {
        SniperEvent.DISCOUNT_SIGNAL: SniperState.OPPORTUNITY_DETECTED,
        SniperEvent.HALT: SniperState.HALTED,
    },
    SniperState.OPPORTUNITY_DETECTED: {
        SniperEvent.ORDER_PLACED: SniperState.AWAITING_FILL,
        SniperEvent.ERROR: SniperState.FAILED,
    },
    SniperState.AWAITING_FILL: {
        SniperEvent.FILL_DETECTED: SniperState.AWAITING_FILL,
        SniperEvent.POSITION_SOLD: SniperState.COMPLETED,
        SniperEvent.ERROR: SniperState.FAILED,
    },
    SniperState.HALTED: {
        SniperEvent.RESUME: SniperState.IDLE,
    },
}


class SniperStateMachine:
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.state: SniperState = SniperState.IDLE
        self.history: List[tuple[SniperState, SniperEvent, datetime]] = []
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = self.created_at

    def transition(self, event: SniperEvent) -> SniperState:
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

    def can_transition(self, event: SniperEvent) -> bool:
        return event in TRANSITIONS.get(self.state, {})

    def is_terminal(self) -> bool:
        return self.state in (SniperState.COMPLETED, SniperState.FAILED)

    def is_active(self) -> bool:
        return self.state not in (SniperState.COMPLETED, SniperState.FAILED, SniperState.HALTED)

    def reset(self) -> None:
        self.state = SniperState.IDLE
        self.history = []
        self.updated_at = datetime.now(timezone.utc)
