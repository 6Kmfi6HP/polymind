"""
Tests for Sniper state machine.
"""

from __future__ import annotations

import pytest
from polymind.workflows.sniper.state_machine import SniperEvent, SniperState, SniperStateMachine


class TestSniperStateMachine:
    def test_initial_state(self):
        sm = SniperStateMachine("sn-001")
        assert sm.state == SniperState.IDLE

    def test_start_watching(self):
        sm = SniperStateMachine("sn-002")
        sm.transition(SniperEvent.START)
        assert sm.state == SniperState.WATCHING

    def test_discount_signal(self):
        sm = SniperStateMachine("sn-003")
        sm.transition(SniperEvent.START)
        sm.transition(SniperEvent.DISCOUNT_SIGNAL)
        assert sm.state == SniperState.OPPORTUNITY_DETECTED

    def test_full_lifecycle(self):
        sm = SniperStateMachine("sn-004")
        sm.transition(SniperEvent.START)
        sm.transition(SniperEvent.DISCOUNT_SIGNAL)
        sm.transition(SniperEvent.ORDER_PLACED)
        assert sm.state == SniperState.AWAITING_FILL
        sm.transition(SniperEvent.POSITION_SOLD)
        assert sm.state == SniperState.COMPLETED

    def test_invalid_transition(self):
        sm = SniperStateMachine("sn-005")
        with pytest.raises(ValueError, match="Invalid transition"):
            sm.transition(SniperEvent.POSITION_SOLD)

    def test_halt_resume(self):
        sm = SniperStateMachine("sn-006")
        sm.transition(SniperEvent.START)
        sm.transition(SniperEvent.HALT)
        assert sm.state == SniperState.HALTED
        sm.transition(SniperEvent.RESUME)
        assert sm.state == SniperState.IDLE

    def test_fill_detected_keeps_state(self):
        sm = SniperStateMachine("sn-007")
        sm.transition(SniperEvent.START)
        sm.transition(SniperEvent.DISCOUNT_SIGNAL)
        sm.transition(SniperEvent.ORDER_PLACED)
        sm.transition(SniperEvent.FILL_DETECTED)
        assert sm.state == SniperState.AWAITING_FILL

    def test_history(self):
        sm = SniperStateMachine("sn-008")
        sm.transition(SniperEvent.START)
        assert len(sm.history) == 1

    def test_reset(self):
        sm = SniperStateMachine("sn-009")
        sm.transition(SniperEvent.START)
        sm.reset()
        assert sm.state == SniperState.IDLE
        assert len(sm.history) == 0
