"""
Tests for Event MM state machine.
"""

from __future__ import annotations

import pytest

from polymind.workflows.event_mm.state_machine import (
    EventMMEvent,
    EventMMState,
    EventMMStateMachine,
)


class TestEventMMStateMachine:
    def test_initial_state(self):
        sm = EventMMStateMachine("evt-001")
        assert sm.state == EventMMState.IDLE
        assert sm.is_active() is True

    def test_start_watching(self):
        sm = EventMMStateMachine("evt-002")
        sm.transition(EventMMEvent.START)
        assert sm.state == EventMMState.WATCHING

    def test_event_trigger(self):
        sm = EventMMStateMachine("evt-003")
        sm.transition(EventMMEvent.START)
        sm.transition(EventMMEvent.EVENT_SIGNAL)
        assert sm.state == EventMMState.TRIGGERED

    def test_full_lifecycle(self):
        sm = EventMMStateMachine("evt-004")
        sm.transition(EventMMEvent.START)
        sm.transition(EventMMEvent.EVENT_SIGNAL)
        sm.transition(EventMMEvent.ORDERS_PLACED)
        assert sm.state == EventMMState.AWAITING_FILLS
        sm.transition(EventMMEvent.POSITION_CLOSED)
        assert sm.state == EventMMState.COOLDOWN
        sm.transition(EventMMEvent.COOLDOWN_DONE)
        assert sm.state == EventMMState.COMPLETED
        assert sm.is_terminal() is True

    def test_invalid_transition(self):
        sm = EventMMStateMachine("evt-005")
        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition(EventMMEvent.COOLDOWN_DONE)

    def test_halt_resume(self):
        sm = EventMMStateMachine("evt-006")
        sm.transition(EventMMEvent.START)
        sm.transition(EventMMEvent.HALT)
        assert sm.state == EventMMState.HALTED
        sm.transition(EventMMEvent.RESUME)
        assert sm.state == EventMMState.IDLE

    def test_fill_multiple_times(self):
        """FILL_DETECTED while awaiting fills should stay in same state."""
        sm = EventMMStateMachine("evt-007")
        sm.transition(EventMMEvent.START)
        sm.transition(EventMMEvent.EVENT_SIGNAL)
        sm.transition(EventMMEvent.ORDERS_PLACED)
        sm.transition(EventMMEvent.FILL_DETECTED)
        assert sm.state == EventMMState.AWAITING_FILLS
        sm.transition(EventMMEvent.FILL_DETECTED)
        assert sm.state == EventMMState.AWAITING_FILLS

    def test_halt_from_watching(self):
        sm = EventMMStateMachine("evt-008")
        sm.transition(EventMMEvent.START)
        sm.transition(EventMMEvent.HALT)
        assert sm.state == EventMMState.HALTED
        assert sm.is_active() is False

    def test_can_transition(self):
        sm = EventMMStateMachine("evt-009")
        assert sm.can_transition(EventMMEvent.START) is True
        assert sm.can_transition(EventMMEvent.COOLDOWN_DONE) is False

    def test_reset(self):
        sm = EventMMStateMachine("evt-010")
        sm.transition(EventMMEvent.START)
        sm.transition(EventMMEvent.EVENT_SIGNAL)
        sm.reset()
        assert sm.state == EventMMState.IDLE
        assert len(sm.history) == 0

    def test_paper_mode_defaults_to_false(self):
        sm = EventMMStateMachine("evt-011")
        assert sm.paper_mode is False
        assert sm.is_paper_mode is False

    def test_paper_mode_can_be_set_to_true(self):
        sm = EventMMStateMachine("evt-012", paper_mode=True)
        assert sm.paper_mode is True
        assert sm.is_paper_mode is True

    def test_is_paper_mode_property(self):
        sm = EventMMStateMachine("evt-013", paper_mode=True)
        assert sm.is_paper_mode is True
        assert isinstance(sm.is_paper_mode, bool)
        sm2 = EventMMStateMachine("evt-014", paper_mode=False)
        assert sm2.is_paper_mode is False
