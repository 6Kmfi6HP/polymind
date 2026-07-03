"""
Tests for Maker Rebate state machine.
"""

from __future__ import annotations

import pytest

from polymind.workflows.maker_rebate.state_machine import (
    RebateEvent,
    RebateState,
    RebateStateMachine,
)


class TestRebateStateMachine:
    def test_initial_state(self):
        sm = RebateStateMachine("wf-001")
        assert sm.state == RebateState.IDLE
        assert sm.workflow_id == "wf-001"
        assert sm.is_active() is True
        assert sm.is_terminal() is False

    def test_start_transition(self):
        sm = RebateStateMachine("wf-001")
        sm.transition(RebateEvent.START)
        assert sm.state == RebateState.PLACING_ORDERS

    def test_full_lifecycle(self):
        sm = RebateStateMachine("wf-001")
        sm.transition(RebateEvent.START)
        sm.transition(RebateEvent.ORDERS_PLACED)
        assert sm.state == RebateState.AWAITING_FILLS
        sm.transition(RebateEvent.ALL_FILLED)
        assert sm.state == RebateState.FILLS_COMPLETE
        # FILLS_COMPLETE → MERGE_DONE → MERGING
        sm.transition(RebateEvent.MERGE_DONE)
        assert sm.state == RebateState.MERGING
        sm.transition(RebateEvent.REDEEM_DONE)
        assert sm.state == RebateState.REDEEMING
        sm.transition(RebateEvent.REDEEM_DONE)
        assert sm.state == RebateState.COMPLETED
        assert sm.is_terminal() is True

    def test_invalid_transition_raises(self):
        sm = RebateStateMachine("wf-002")
        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition(RebateEvent.ALL_FILLED)  # can't jump to fills from idle

    def test_halt_and_resume(self):
        sm = RebateStateMachine("wf-003")
        sm.transition(RebateEvent.START)
        sm.transition(RebateEvent.HALT)
        assert sm.state == RebateState.HALTED
        assert sm.is_active() is False
        sm.transition(RebateEvent.RESUME)
        assert sm.state == RebateState.IDLE
        assert sm.is_active() is True

    def test_can_transition(self):
        sm = RebateStateMachine("wf-004")
        assert sm.can_transition(RebateEvent.START) is True
        assert sm.can_transition(RebateEvent.ALL_FILLED) is False

    def test_history_recorded(self):
        sm = RebateStateMachine("wf-005")
        sm.transition(RebateEvent.START)
        sm.transition(RebateEvent.ORDERS_PLACED)
        assert len(sm.history) == 2
        assert sm.history[0][0] == RebateState.IDLE
        assert sm.history[0][1] == RebateEvent.START
        assert sm.history[1][1] == RebateEvent.ORDERS_PLACED

    def test_reset(self):
        sm = RebateStateMachine("wf-006")
        sm.transition(RebateEvent.START)
        sm.reset()
        assert sm.state == RebateState.IDLE
        assert len(sm.history) == 0

    def test_error_transition(self):
        sm = RebateStateMachine("wf-007")
        sm.transition(RebateEvent.START)
        sm.transition(RebateEvent.ERROR)
        assert sm.state == RebateState.FAILED
        assert sm.is_terminal() is True

    def test_multiple_fill_events(self):
        """FILL_DETECTED while in AWAITING_FILLS should stay in same state."""
        sm = RebateStateMachine("wf-008")
        sm.transition(RebateEvent.START)
        sm.transition(RebateEvent.ORDERS_PLACED)
        sm.transition(RebateEvent.FILL_DETECTED)
        assert sm.state == RebateState.AWAITING_FILLS
        sm.transition(RebateEvent.FILL_DETECTED)
        assert sm.state == RebateState.AWAITING_FILLS
        sm.transition(RebateEvent.ALL_FILLED)
        assert sm.state == RebateState.FILLS_COMPLETE
