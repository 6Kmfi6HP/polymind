"""
Event MM workflow state machine.

Event-driven market making reacts to external events (news, announcements,
price movements). The state machine tracks the lifecycle from idle watching
through cooldown after an event trigger.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum, auto


class EventMMState(Enum):
    """Lifecycle states for an Event MM workflow instance."""

    IDLE = auto()
    WATCHING = auto()
    TRIGGERED = auto()
    PLACING_ORDERS = auto()
    AWAITING_FILLS = auto()
    COOLDOWN = auto()
    COMPLETED = auto()
    FAILED = auto()
    HALTED = auto()


class EventMMEvent(Enum):
    """Events that trigger state transitions."""

    START = auto()
    EVENT_SIGNAL = auto()
    ORDERS_PLACED = auto()
    FILL_DETECTED = auto()
    POSITION_CLOSED = auto()
    COOLDOWN_DONE = auto()
    ERROR = auto()
    HALT = auto()
    RESUME = auto()


TRANSITIONS: dict[EventMMState, dict[EventMMEvent, EventMMState]] = {
    EventMMState.IDLE: {
        EventMMEvent.START: EventMMState.WATCHING,
        EventMMEvent.HALT: EventMMState.HALTED,
    },
    EventMMState.WATCHING: {
        EventMMEvent.EVENT_SIGNAL: EventMMState.TRIGGERED,
        EventMMEvent.HALT: EventMMState.HALTED,
    },
    EventMMState.TRIGGERED: {
        EventMMEvent.ORDERS_PLACED: EventMMState.AWAITING_FILLS,
        EventMMEvent.ERROR: EventMMState.FAILED,
    },
    EventMMState.AWAITING_FILLS: {
        EventMMEvent.FILL_DETECTED: EventMMState.AWAITING_FILLS,
        EventMMEvent.POSITION_CLOSED: EventMMState.COOLDOWN,
        EventMMEvent.ERROR: EventMMState.FAILED,
    },
    EventMMState.COOLDOWN: {
        EventMMEvent.COOLDOWN_DONE: EventMMState.COMPLETED,
        EventMMEvent.ERROR: EventMMState.FAILED,
    },
    EventMMState.HALTED: {
        EventMMEvent.RESUME: EventMMState.IDLE,
    },
}


class EventMMStateMachine:
    """State machine for a single Event MM workflow instance."""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.state: EventMMState = EventMMState.IDLE
        self.history: list[tuple[EventMMState, EventMMEvent, datetime]] = []
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = self.created_at

    def transition(self, event: EventMMEvent) -> EventMMState:
        """Apply an event and transition to the next state."""
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

    def can_transition(self, event: EventMMEvent) -> bool:
        return event in TRANSITIONS.get(self.state, {})

    def is_terminal(self) -> bool:
        return self.state in (EventMMState.COMPLETED, EventMMState.FAILED)

    def is_active(self) -> bool:
        return self.state not in (
            EventMMState.COMPLETED,
            EventMMState.FAILED,
            EventMMState.HALTED,
        )

    def reset(self) -> None:
        self.state = EventMMState.IDLE
        self.history = []
        self.updated_at = datetime.now(timezone.utc)
