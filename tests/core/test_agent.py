"""
Tests for BaseAgent.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.agent import BaseAgent, Decision, Observation


class TestObservation:
    def test_minimal(self):
        now = datetime.now()
        obs = Observation(timestamp=now, markets=[], positions=[])
        assert obs.timestamp == now
        assert obs.markets == []
        assert obs.positions == []


class TestBaseAgent:
    class _TestAgent(BaseAgent):
        """Concrete agent for testing."""
        def __init__(self):
            super().__init__(name="test_agent", loop_interval=1)

        async def decide(self, observation: Observation) -> Decision:
            return Decision(action="hold", reasoning="no action needed")

    @pytest.mark.asyncio
    async def test_agent_name(self):
        agent = self._TestAgent()
        assert agent.name == "test_agent"

    @pytest.mark.asyncio
    async def test_decide(self):
        agent = self._TestAgent()
        now = datetime.now()
        obs = Observation(timestamp=now, markets=["m1", "m2"])
        decision = await agent.decide(obs)
        assert decision.action == "hold"
        assert decision.reasoning == "no action needed"

    @pytest.mark.asyncio
    async def test_act_hold(self):
        agent = self._TestAgent()
        decision = Decision(action="hold")
        result = await agent.act(decision)
        assert result is True

    @pytest.mark.asyncio
    async def test_dry_run(self):
        agent = self._TestAgent()
        agent.dry_run = True
        decision = Decision(action="buy", market_id="0xabc", size=10.0, price=0.5)
        result = await agent.act(decision)
        assert result is True

    @pytest.mark.asyncio
    async def test_stop(self):
        agent = self._TestAgent()
        assert agent._running is False
        agent.stop()

    @pytest.mark.asyncio
    async def test_loop_interval(self):
        agent = self._TestAgent()
        assert agent.loop_interval == 1
        assert agent.dry_run is False
