"""
Tests for RiskDecision, RiskGate, and RiskContext.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.core.intents import StrategyIntent
from polymind.core.risk import RiskContext, RiskDecision, RiskGate


class TestRiskDecision:
    def test_approved_decision(self):
        decision = RiskDecision(
            gate_name="exposure_limit",
            approved=True,
            reason="Within limits",
        )
        assert decision.gate_name == "exposure_limit"
        assert decision.approved is True
        assert decision.reason == "Within limits"
        assert decision.timestamp is not None

    def test_rejected_decision(self):
        decision = RiskDecision(
            gate_name="drawdown_guard",
            approved=False,
            reason="Daily loss limit exceeded",
            overrides={"reduce_size_pct": 50.0},
        )
        assert decision.approved is False
        assert decision.overrides == {"reduce_size_pct": 50.0}

    def test_timestamp_auto_set(self):
        before = datetime.now(timezone.utc)
        decision = RiskDecision(gate_name="kill_switch", approved=True, reason="All clear")
        after = datetime.now(timezone.utc)
        assert before <= decision.timestamp <= after


class TestRiskContext:
    def test_full_construction(self):
        ctx = RiskContext(
            current_positions={"0xabc": 10.0},
            current_exposure=500.0,
            daily_pnl=-25.0,
            is_kill_switch_active=False,
            portfolio_value=1000.0,
        )
        assert ctx.current_positions["0xabc"] == 10.0
        assert ctx.current_exposure == 500.0
        assert ctx.daily_pnl == -25.0
        assert ctx.is_kill_switch_active is False
        assert ctx.portfolio_value == 1000.0

    def test_kill_switch_active(self):
        ctx = RiskContext(
            current_positions={},
            current_exposure=0.0,
            daily_pnl=0.0,
            is_kill_switch_active=True,
            portfolio_value=1000.0,
        )
        assert ctx.is_kill_switch_active is True


class TestRiskGate:
    @pytest.mark.asyncio
    async def test_gate_can_approve(self):
        gate = AllowAllGate()
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(timestamp=now, strategy_name="test")
        ctx = RiskContext(
            current_positions={},
            current_exposure=0.0,
            daily_pnl=0.0,
            is_kill_switch_active=False,
            portfolio_value=1000.0,
        )
        decision = await gate.evaluate(intent, ctx)
        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_gate_can_reject(self):
        gate = RejectAllGate()
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(timestamp=now, strategy_name="test")
        ctx = RiskContext(
            current_positions={},
            current_exposure=0.0,
            daily_pnl=0.0,
            is_kill_switch_active=True,
            portfolio_value=1000.0,
        )
        decision = await gate.evaluate(intent, ctx)
        assert decision.approved is False

    @pytest.mark.asyncio
    async def test_gate_name_preserved(self):
        gate = AllowAllGate()
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(timestamp=now, strategy_name="test")
        ctx = RiskContext(
            current_positions={},
            current_exposure=0.0,
            daily_pnl=0.0,
            is_kill_switch_active=False,
            portfolio_value=1000.0,
        )
        decision = await gate.evaluate(intent, ctx)
        assert decision.gate_name == "AllowAllGate"


class AllowAllGate(RiskGate):
    """Test gate that always approves."""

    name = "AllowAllGate"

    async def evaluate(self, intent: StrategyIntent, context: RiskContext) -> RiskDecision:
        return RiskDecision(
            gate_name=self.name,
            approved=True,
            reason="Always allow (test)",
        )


class RejectAllGate(RiskGate):
    """Test gate that always rejects."""

    name = "RejectAllGate"

    async def evaluate(self, intent: StrategyIntent, context: RiskContext) -> RiskDecision:
        return RiskDecision(
            gate_name=self.name,
            approved=False,
            reason="Always reject (test)",
        )
