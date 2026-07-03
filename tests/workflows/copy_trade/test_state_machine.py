"""
Tests for Copy Trade state machine.
"""

from __future__ import annotations

import pytest
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
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        assert sm.state == CopyTradeState.TRADE_DETECTED

    def test_full_lifecycle(self):
        sm = CopyTradeStateMachine("ct-004")
        sm.transition(CopyTradeEvent.START)
        sm.transition(CopyTradeEvent.TARGET_TRADE)
        sm.transition(CopyTradeEvent.ANALYSIS_DONE)
        assert sm.state == CopyTradeState.PLACING_ORDER
        sm.transition(CopyTradeEvent.ORDER_PLACED)
        assert sm.state == CopyTradeState.AWAITING_FILL

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
        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition(CopyTradeEvent.ORDER_PLACED)

    def test_halt_resume(self):
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
        assert sm.is_active() is True
        assert sm.is_terminal() is False
