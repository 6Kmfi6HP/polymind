"""
Tests for Copy Trade state machine.
"""

from __future__ import annotations

import pytest
<<<<<<< HEAD
from polymind.workflows.copy_trade.state_machine import CopyTradeEvent, CopyTradeState, CopyTradeStateMachine


class TestCopyTradeStateMachine:
    def test_initial_state(self):
        sm = CopyTradeStateMachine("ct-001")
        assert sm.state == CopyTradeState.IDLE

    def test_start_monitoring(self):
        sm = CopyTradeStateMachine("ct-002")
        sm.transition(CopyTradeEvent.START)
        assert sm.state == CopyTradeState.MONITORING

    def test_target_trade_detected(self):
        sm = CopyTradeStateMachine("ct-003")
=======

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
>>>>>>> b5faa97 (feat(factors): add PortfolioConstructor with rank-based sizing)
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        assert sm.state == CopyTradeState.TRADE_DETECTED

<<<<<<< HEAD
    def test_full_lifecycle(self):
        sm = CopyTradeStateMachine("ct-004")
=======
    def test_analysis_then_placing_order(self):
        sm = CopyTradeStateMachine(workflow_id="ct-004")
>>>>>>> b5faa97 (feat(factors): add PortfolioConstructor with rank-based sizing)
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        sm.transition(CopyTradeEvent.ANALYSIS_DONE)
        assert sm.state == CopyTradeState.PLACING_ORDER
        sm.transition(CopyTradeEvent.ORDER_PLACED)
        assert sm.state == CopyTradeState.AWAITING_FILL

<<<<<<< HEAD
    def test_back_to_monitoring_after_fill(self):
        sm = CopyTradeStateMachine("ct-005")
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        sm.transition(CopyTradeEvent.ANALYSIS_DONE)
        sm.transition(CopyTradeEvent.ORDER_PLACED)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        assert sm.state == CopyTradeState.MONITORING

    def test_invalid_transition(self):
        sm = CopyTradeStateMachine("ct-006")
=======
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
>>>>>>> b5faa97 (feat(factors): add PortfolioConstructor with rank-based sizing)
        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition(CopyTradeEvent.ORDER_PLACED)

    def test_halt_resume(self):
<<<<<<< HEAD
        sm = CopyTradeStateMachine("ct-007")
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.HALT)
        assert sm.state == CopyTradeState.HALTED
        sm.transition(CopyTradeEvent.RESUME)
        assert sm.state == CopyTradeState.IDLE

    def test_history(self):
        sm = CopyTradeStateMachine("ct-008")
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        assert len(sm.history) == 2

    def test_reset(self):
        sm = CopyTradeStateMachine("ct-009")
        sm.transition(CopyTradeEvent.START)
        sm.reset()
        assert sm.state == CopyTradeState.IDLE

    def test_is_active_terminal(self):
        sm = CopyTradeStateMachine("ct-010")
=======
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
>>>>>>> b5faa97 (feat(factors): add PortfolioConstructor with rank-based sizing)
        assert sm.is_active() is True
        assert sm.is_terminal() is False
