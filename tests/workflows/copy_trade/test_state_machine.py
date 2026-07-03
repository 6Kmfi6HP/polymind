"""
Tests for Copy Trade state machine.
"""

from __future__ import annotations

import pytest

from polymind.workflows.copy_trade.state_machine import (
    CopyTradeEvent,
    CopyTradeState,
    CopyTradeStateMachine,
)


class TestCopyTradeStateMachine:
    """10 tests for CopyTradeStateMachine."""

    def test_initial_state(self):
        sm = CopyTradeStateMachine(workflow_id="ct-001")
        assert sm.workflow_id == "ct-001"
        assert sm.state == CopyTradeState.IDLE
        assert sm.is_active() is True
        assert sm.is_terminal() is False
        assert sm.history == []

    def test_start_monitoring(self):
        sm = CopyTradeStateMachine(workflow_id="ct-002")
        sm.transition(CopyTradeEvent.START)
        assert sm.state == CopyTradeState.MONITORING
        assert len(sm.history) == 1
        assert sm.history[0][0] == CopyTradeState.IDLE
        assert sm.history[0][1] == CopyTradeEvent.START

    def test_detect_target_trade(self):
        sm = CopyTradeStateMachine(workflow_id="ct-003")
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        assert sm.state == CopyTradeState.TRADE_DETECTED

    def test_analysis_then_placing_order(self):
        sm = CopyTradeStateMachine(workflow_id="ct-004")
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        sm.transition(CopyTradeEvent.ANALYSIS_DONE)
        assert sm.state == CopyTradeState.PLACING_ORDER
        sm.transition(CopyTradeEvent.ORDER_PLACED)
        assert sm.state == CopyTradeState.AWAITING_FILL

    def test_full_lifecycle(self):
        sm = CopyTradeStateMachine(workflow_id="ct-005")
        sm.transition(CopyTradeEvent.START)
        assert sm.state == CopyTradeState.MONITORING
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        assert sm.state == CopyTradeState.TRADE_DETECTED
        sm.transition(CopyTradeEvent.ANALYSIS_DONE)
        assert sm.state == CopyTradeState.PLACING_ORDER
        sm.transition(CopyTradeEvent.ORDER_PLACED)
        assert sm.state == CopyTradeState.AWAITING_FILL
        sm.transition(CopyTradeEvent.FILL_DETECTED)
        assert sm.state == CopyTradeState.AWAITING_FILL
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        assert sm.state == CopyTradeState.MONITORING

    def test_invalid_transition_raises(self):
        sm = CopyTradeStateMachine(workflow_id="ct-006")
        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition(CopyTradeEvent.ORDER_PLACED)

    def test_halt_resume(self):
        sm = CopyTradeStateMachine(workflow_id="ct-007")
        sm.transition(CopyTradeEvent.START)
        assert sm.state == CopyTradeState.MONITORING
        sm.transition(CopyTradeEvent.HALT)
        assert sm.state == CopyTradeState.HALTED
        assert sm.is_active() is False
        sm.transition(CopyTradeEvent.RESUME)
        assert sm.state == CopyTradeState.IDLE
        assert sm.is_active() is True

    def test_error_leads_to_failed(self):
        sm = CopyTradeStateMachine(workflow_id="ct-008")
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        sm.transition(CopyTradeEvent.ERROR)
        assert sm.state == CopyTradeState.FAILED
        assert sm.is_terminal() is True
        assert sm.is_active() is False

    def test_can_transition(self):
        sm = CopyTradeStateMachine(workflow_id="ct-009")
        assert sm.can_transition(CopyTradeEvent.START) is True
        assert sm.can_transition(CopyTradeEvent.HALT) is True
        assert sm.can_transition(CopyTradeEvent.ORDER_PLACED) is False
        sm.transition(CopyTradeEvent.START)
        assert sm.can_transition(CopyTradeEvent.TARGET_TRADE) is True
        assert sm.can_transition(CopyTradeEvent.HALT) is True
        assert sm.can_transition(CopyTradeEvent.START) is False

    def test_reset(self):
        sm = CopyTradeStateMachine(workflow_id="ct-010")
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        assert sm.state != CopyTradeState.IDLE
        assert len(sm.history) == 2
        assert sm.is_active() is True
        sm.reset()
        assert sm.state == CopyTradeState.IDLE
        assert sm.history == []
        assert sm.is_active() is True
        assert sm.is_terminal() is False
